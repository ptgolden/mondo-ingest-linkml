"""Turn an extract into a SourceRelease: the step every source shares.

An extract is what a source states, in the schema's own terms: its Terms, and what it
says about itself. extract.py makes one from an RDF source.

Building the Pydantic models generated from the schema (datamodel.py) checks types,
required slots, CURIE patterns and unknown slots.
"""

import pydantic

from mondo_source.datamodel import ReleaseMetadata, SourceRelease, Term


class Extract(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    metadata: dict[str, str]
    """What the source says about itself: ReleaseMetadata's source_* slots."""

    terms: list[Term]


def finalize(extract: Extract, pipeline_metadata: dict[str, str]) -> SourceRelease:
    """pipeline_metadata: the ReleaseMetadata slots the build knows, not the source."""
    metadata = ReleaseMetadata.model_validate({**extract.metadata, **pipeline_metadata})
    return SourceRelease(metadata=metadata, terms=extract.terms)
