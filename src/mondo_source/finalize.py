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


def standardise(
    value: pydantic.JsonValue, path: SlotPath, identifiers: frozenset[SlotPath], converter: curies.Converter
) -> pydantic.JsonValue:
    """value, found at path in a term, with its identifiers as canonical CURIEs."""
    match value:
        case dict():
            return {slot: standardise(v, (*path, slot), identifiers, converter) for slot, v in value.items()}
        case list():
            return [standardise(v, path, identifiers, converter) for v in value]
        case str() if path in identifiers:
            curie = converter.compress_or_standardize(value)
            if curie is None:
                raise ValueError(f"{'.'.join(path)}: no prefix in the prefix map for {value!r}")
            return curie
        case _:
            return value


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
    identifiers = frozenset(identifier_slots(schema, "Term"))
    terms = []
    for stated in extract.terms:
        try:
            term = Term.model_validate(standardise(stated, (), identifiers, converter))
        except ValueError as e:
            raise ValueError(f"{stated.get('id')}: {e}") from e
        sort_values(term)
        terms.append(term)

    metadata = ReleaseMetadata.model_validate({**extract.metadata, **pipeline_metadata})
    return SourceRelease(metadata=metadata, terms=sorted(terms, key=lambda term: term.id))
