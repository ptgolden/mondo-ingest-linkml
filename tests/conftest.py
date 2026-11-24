"""The tests import datamodel.py, which a source's make generates from the schema.
It is generated here as well, when it is missing or older than the schema."""

from pathlib import Path

import sssom_schema
from linkml.generators.pydanticgen import PydanticGenerator

PACKAGE = Path(__file__).parent.parent / "src" / "mondo_source"
SCHEMA = PACKAGE / "schema" / "mondo_source.yaml"
MODELS = PACKAGE / "datamodel.py"
IMPORTMAP = {"sssom_schema:": f"{Path(sssom_schema.__file__).parent / 'schema'}/"}

if not MODELS.exists() or MODELS.stat().st_mtime < SCHEMA.stat().st_mtime:
    MODELS.write_text(PydanticGenerator(str(SCHEMA), importmap=IMPORTMAP).serialize())
