"""Turn an extract into a SourceRelease: the step every source shares.

An extract is what a source states: its terms, in the shape of the schema's Term, and
what it says about itself. extract.py makes one from an RDF source. Its identifiers are
as the source has them: IRIs, or CURIEs in the source's own spelling of the prefix.
That is all that keeps its terms from being Terms, whose identifier slots have
patterns.

Here the identifiers are standardised with the prefix map, so each becomes the
canonical CURIE (ORDO's "ICD-10:" and "MeSH:" become "ICD10:" and "MESH:"). The schema
says which slots hold identifiers. Each term is then built as the Pydantic model
generated from the schema (datamodel.py), which checks types, required slots, CURIE
patterns and unknown slots.

Mondo's own synonyms are then added to each term, typed as generated: its label, for
every source, and its bracket-stripped names, for the sources that ask.

Terms are sorted by id, and the values of each multivalued slot are sorted, so the
release doesn't depend on the order a source gives things in.
"""

import re

from collections.abc import Iterator
from dataclasses import dataclass

import curies
import pydantic
from linkml_runtime.utils.schemaview import SchemaView

from mondo_source.datamodel import (
    ReleaseMetadata,
    Relationship,
    SourceRelease,
    Synonym,
    SynonymScope,
    Term,
    TermMapping,
)

type SlotPath = tuple[str, ...]
"""A slot of Term, or of an object nested in one: ("parents",), ("mappings", "object_id")."""


class Extract(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    metadata: dict[str, str]
    """What the source says about itself: ReleaseMetadata's source_* slots."""

    terms: list[dict[str, pydantic.JsonValue]]
    """Each in the shape of a Term."""


def identifier_slots(schema: SchemaView, class_name: str, path: SlotPath = ()) -> Iterator[SlotPath]:
    """The slots of a class, and of the objects nested in it, that hold identifiers."""
    for slot in schema.class_induced_slots(class_name):
        assert slot.range is not None  # an induced slot has its own or the schema's default
        here = (*path, slot.name)
        if slot.range in schema.all_classes():
            # A class with an identifier is referred to by it (Term.parents); one
            # without is nested (Term.synonyms).
            if schema.get_identifier_slot(slot.range):
                yield here
            else:
                yield from identifier_slots(schema, slot.range, here)
        elif slot.range in schema.all_types() and "uriorcurie" in schema.type_ancestors(slot.range):
            yield here


@dataclass(frozen=True)
class Identifiers:
    """The slots that hold identifiers, and the prefix map their CURIEs come from."""

    slots: frozenset[SlotPath]
    converter: curies.Converter

    def to_curies(self, stated: pydantic.JsonValue, path: SlotPath = ()) -> pydantic.JsonValue:
        """A stated term, or the part of one at path, with each identifier as its
        canonical CURIE."""
        match stated:
            case dict():
                return {slot: self.to_curies(value, (*path, slot)) for slot, value in stated.items()}
            case list():
                return [self.to_curies(value, path) for value in stated]
            case str() if path in self.slots:
                return self.curie(stated, path)
            case _:
                return stated

    def curie(self, identifier: str, slot: SlotPath) -> str:
        """The canonical CURIE for an IRI, or for a CURIE in any spelling of its prefix."""
        curie = self.converter.compress_or_standardize(identifier)
        if curie is None:
            raise ValueError(f"{'.'.join(slot)}: no prefix in the prefix map for {identifier!r}")
        return curie


SYNONYM_TYPE: SlotPath = ("synonyms", "synonym_type")
GENERATED_FROM_LABEL = "http://purl.obolibrary.org/obo/mondo#GENERATED_FROM_LABEL"
GENERATED = "http://purl.obolibrary.org/obo/mondo#GENERATED"

# "\Z", not "$": the end of the text, as in the SPARQL these came from, and not also
# before a final newline.
ENDS_IN_BRACKET = re.compile(r"[\])]\Z")
FINAL_BRACKETED_PART = re.compile(r" [\[(].*[)\]]\Z")


def generated(text: str, synonym_type: str, identifiers: Identifiers) -> Synonym:
    return Synonym(text=text, scope=SynonymScope.EXACT, synonym_type=identifiers.curie(synonym_type, SYNONYM_TYPE))


def bracket_stripped(term: Term) -> set[str]:
    """The label and each exact synonym of a term that end in ")" or "]", lowercased
    and without the final bracketed part (mondo-ingest's fix-labels-with-brackets.ru):
    "Leprosy [Hansen disease]" gives "leprosy".

    As there, the part goes only if a space comes before its opening bracket:
    "pericytoma with t(7;12)" is lowercased and nothing more.
    """
    exact = [synonym.text for synonym in term.synonyms or [] if synonym.scope == SynonymScope.EXACT]
    bracketed = [text for text in (term.label, *exact) if ENDS_IN_BRACKET.search(text)]
    return {FINAL_BRACKETED_PART.sub("", text.lower()) for text in bracketed}


def mondo_synonyms(term: Term, identifiers: Identifiers, strip_brackets: bool) -> list[Synonym]:
    """The synonyms Mondo adds to a term, all EXACT:

    - the label of a term that isn't deprecated, typed mondo:GENERATED_FROM_LABEL
      (mondo-ingest's exact_syn_from_label.ru), for every source;
    - bracket_stripped(), typed mondo:GENERATED, for the sources that ask for it.
    """
    from_label = [] if term.deprecated else [term.label]
    stripped = bracket_stripped(term) if strip_brackets else set()
    return [
        *(generated(text, GENERATED_FROM_LABEL, identifiers) for text in from_label),
        *(generated(text, GENERATED, identifiers) for text in stripped),
    ]


def sort_key(value: str | Synonym | Relationship | TermMapping) -> tuple[str, ...]:
    """Where a value of a multivalued slot of Term goes among the others."""
    match value:
        case str():
            return (value,)
        case Synonym():
            return (value.text, value.scope, value.synonym_type or "")
        case Relationship():
            return (value.predicate, value.target)
        case TermMapping():
            # By object, then predicate; the rest only so that the order is total.
            return (value.object_id, value.predicate_id or "", value.model_dump_json())


def sort_values(term: Term) -> None:
    for slot in Term.model_fields:
        values = getattr(term, slot)
        if isinstance(values, list):
            values.sort(key=sort_key)


def finalize(
    extract: Extract,
    converter: curies.Converter,
    schema: SchemaView,
    pipeline_metadata: dict[str, str],
    strip_brackets: bool = False,
) -> SourceRelease:
    """pipeline_metadata: the ReleaseMetadata slots the build knows, not the source.
    schema_version is the schema's own."""
    identifiers = Identifiers(frozenset(identifier_slots(schema, "Term")), converter)
    terms = []
    for stated in extract.terms:
        try:
            term = Term.model_validate(identifiers.to_curies(stated))
        except ValueError as e:
            raise ValueError(f"{stated.get('id')}: {e}") from e
        term.synonyms = [*(term.synonyms or []), *mondo_synonyms(term, identifiers, strip_brackets)] or None
        sort_values(term)
        terms.append(term)

    assert schema.schema is not None
    metadata = ReleaseMetadata.model_validate(
        {**extract.metadata, **pipeline_metadata, "schema_version": schema.schema.version}
    )
    return SourceRelease(metadata=metadata, terms=sorted(terms, key=lambda term: term.id))
