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

Two things are then checked across the terms: no two have the same id, and every
parent is a term of the release.

A term that can't be built doesn't stop the others. Everything wrong with the extract
is raised together, as Problems.
"""

from collections import Counter

import curies
import pydantic
from linkml_runtime.utils.schemaview import SchemaView

from mondo_source.datamodel import ReleaseMetadata, Relationship, SourceRelease, Synonym, Term, TermMapping
from mondo_source.identifiers import Identifiers, identifier_slots
from mondo_source.mondo_synonyms import mondo_synonyms
from mondo_source.problems import Problem, Problems

type Stated = dict[str, pydantic.JsonValue]


class Extract(pydantic.BaseModel):
    """What a source states, before anything shared is done to it. As JSON, it is the
    file that a source which isn't RDF writes."""

    model_config = pydantic.ConfigDict(extra="forbid")

    metadata: dict[str, str]
    """What the source says about itself: ReleaseMetadata's source_* slots."""

    terms: list[Stated]
    """Each in the shape of a Term."""


def rejected(of: str, error: pydantic.ValidationError) -> list[Problem]:
    """What a model found wrong with a term, or with the metadata."""
    return [
        Problem(
            term=of,
            slot=".".join(part for part in e["loc"] if isinstance(part, str)),
            value=None if e["type"] == "missing" else str(e["input"]),
            problem=e["msg"],
        )
        for e in error.errors()
    ]


def without_empty_lists(stated: Stated) -> Stated:
    """A stated term without the slots it gives an empty list for, which say the same
    as leaving the slot out."""
    return {slot: value for slot, value in stated.items() if value != []}


def term_from(stated: Stated, identifiers: Identifiers) -> Term | list[Problem]:
    """The Term a stated term makes once its identifiers are canonical, or what is
    wrong with it."""
    stated_id = str(stated.get("id", "(no id)"))
    problems = [
        Problem(stated_id, ".".join(slot), identifier, "no prefix in the prefix map")
        for slot, identifier in identifiers.unknown_in(stated)
    ]
    try:
        term = Term.model_validate(identifiers.to_curies(without_empty_lists(stated)))
    except pydantic.ValidationError as e:
        return [*problems, *rejected(stated_id, e)]
    # The schema can't say this of label: see the slot's description there.
    if term.label is None and not term.deprecated:
        problems.append(Problem(stated_id, "label", None, "required unless the term is deprecated"))
    return problems or term


def metadata_from(stated: dict[str, str | list[str] | None]) -> ReleaseMetadata | list[Problem]:
    """The release's metadata, or what is wrong with it."""
    try:
        return ReleaseMetadata.model_validate(stated)
    except pydantic.ValidationError as e:
        return rejected("(metadata)", e)


def repeated_ids(terms: list[Term]) -> list[Problem]:
    """A problem for each id that more than one term has."""
    counts = Counter(term.id for term in terms)
    return [Problem(id, "id", id, f"the id of {count} terms") for id, count in counts.items() if count > 1]


def parents_outside(terms: list[Term]) -> list[Problem]:
    """A problem for each parent that isn't a term of the release."""
    ids = {term.id for term in terms}
    return [
        Problem(term.id, "parents", parent, "not a term of the release")
        for term in terms
        for parent in term.parents or []
        if parent not in ids
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
    """Put the values of each multivalued slot of a term in order."""
    for slot in Term.model_fields:
        values = getattr(term, slot)
        if isinstance(values, list):
            values.sort(key=sort_key)


def finalize(
    extract: Extract,
    converter: curies.Converter,
    schema: SchemaView,
    pipeline_metadata: dict[str, str | list[str]],
    strip_brackets: bool = False,
) -> SourceRelease:
    """The release an extract makes, or Problems.

    pipeline_metadata is the ReleaseMetadata slots that the build knows and the source
    doesn't (source_id, source_download_urls, generated_at, ...); schema_version is
    the schema's own.
    strip_brackets is whether Mondo takes this source's bracket-stripped names
    (mondo_synonyms.py).
    """
    identifiers = Identifiers(frozenset(identifier_slots(schema, "Term")), converter)
    terms: list[Term] = []
    problems: list[Problem] = []
    for stated in extract.terms:
        match term_from(stated, identifiers):
            case Term() as term:
                term.synonyms = [*(term.synonyms or []), *mondo_synonyms(term, identifiers, strip_brackets)] or None
                sort_values(term)
                terms.append(term)
            case list() as found:
                problems += found
    # Only once every term is built: a term that wasn't would be missed as a parent.
    if not problems:
        problems = [*repeated_ids(terms), *parents_outside(terms)]

    assert schema.schema is not None
    match metadata_from({**extract.metadata, **pipeline_metadata, "schema_version": schema.schema.version}):
        case list() as found:
            raise Problems([*problems, *found])
        case _ if problems:
            raise Problems(problems)
        case metadata:
            return SourceRelease(metadata=metadata, terms=sorted(terms, key=lambda term: term.id))
