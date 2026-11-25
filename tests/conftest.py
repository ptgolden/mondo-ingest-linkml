"""The tests import datamodel.py, which a source's make generates from the schema.
It is generated here as well, when it is missing or older than the schema."""

import json
from pathlib import Path

import pytest
import sssom_schema
from linkml.generators.pydanticgen import PydanticGenerator
from linkml_runtime.utils.schemaview import SchemaView

PACKAGE = Path(__file__).parent.parent / "src" / "mondo_source"
SCHEMA = PACKAGE / "schema" / "mondo_source.yaml"
MODELS = PACKAGE / "datamodel.py"
IMPORTMAP = {"sssom_schema:": f"{Path(sssom_schema.__file__).parent / 'schema'}/"}

if not MODELS.exists() or MODELS.stat().st_mtime < SCHEMA.stat().st_mtime:
    MODELS.write_text(PydanticGenerator(str(SCHEMA), importmap=IMPORTMAP).serialize())


@pytest.fixture(scope="session")
def schema() -> SchemaView:
    return SchemaView(str(SCHEMA), importmap=IMPORTMAP)


@pytest.fixture(scope="session")
def schema_file() -> Path:
    return SCHEMA


@pytest.fixture(scope="session")
def importmap_file(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("linkml") / "importmap.json"
    path.write_text(json.dumps(IMPORTMAP))
    return path
