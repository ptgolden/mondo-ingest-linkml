import json
from pathlib import Path

import pytest
from linkml_runtime.utils.schemaview import SchemaView

from mondo_source.importmap import importmap

PACKAGE = Path(__file__).parent.parent / "src" / "mondo_source"
SCHEMA = PACKAGE / "schema" / "mondo_source.yaml"
IMPORTMAP = importmap()


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
