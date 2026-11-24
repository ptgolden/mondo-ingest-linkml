"""Turn an extract into a SourceRelease: the step every source shares.

An extract is what a source states: its terms, in the shape of the schema's Term, and
what it says about itself. extract.py makes one from an RDF source. Its identifiers are
as the source has them, which is all that keeps its terms from being Terms, whose
identifier slots have patterns.

For each term:

- its identifiers are made canonical (identifiers.py);
- it is built as the Pydantic model generated from the schema (datamodel.py), which
  checks types, required slots, CURIE patterns and unknown slots;
- Mondo's own synonyms are added (mondo_synonyms.py);
- the values of each multivalued slot are sorted.

The terms are sorted by id, so the release doesn't depend on the order a source gives
things in.
"""

import curies
import pydantic
from linkml_runtime.utils.schemaview import SchemaView

from mondo_source.datamodel import ReleaseMetadata, Relationship, SourceRelease, Synonym, Term, TermMapping
from mondo_source.identifiers import Identifiers, identifier_slots
from mondo_source.mondo_synonyms import mondo_synonyms


class Extract(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    metadata: dict[str, str]
    """What the source says about itself: ReleaseMetadata's source_* slots."""

    terms: list[dict[str, pydantic.JsonValue]]
    """Each in the shape of a Term."""


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
