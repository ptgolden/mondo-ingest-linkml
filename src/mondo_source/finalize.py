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

Terms are sorted by id, and the values of each multivalued slot are sorted, so the
release doesn't depend on the order a source gives things in.
"""

from collections.abc import Iterator
from dataclasses import dataclass

import curies
import pydantic
from linkml_runtime.utils.schemaview import SchemaView

from mondo_source.datamodel import ReleaseMetadata, Relationship, SourceRelease, Synonym, Term, TermMapping

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
    extract: Extract, converter: curies.Converter, schema: SchemaView, pipeline_metadata: dict[str, str]
) -> SourceRelease:
    """pipeline_metadata: the ReleaseMetadata slots the build knows, not the source."""
    identifiers = Identifiers(frozenset(identifier_slots(schema, "Term")), converter)
    terms = []
    for stated in extract.terms:
        try:
            term = Term.model_validate(identifiers.to_curies(stated))
        except ValueError as e:
            raise ValueError(f"{stated.get('id')}: {e}") from e
        sort_values(term)
        terms.append(term)

    metadata = ReleaseMetadata.model_validate({**extract.metadata, **pipeline_metadata})
    return SourceRelease(metadata=metadata, terms=sorted(terms, key=lambda term: term.id))
