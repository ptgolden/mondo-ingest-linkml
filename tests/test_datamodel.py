from pathlib import Path

from linkml.generators.pydanticgen import PydanticGenerator

from mondo_source.importmap import importmap

ROOT = Path(__file__).parent.parent
SCHEMA = Path("src/mondo_source/schema/mondo_source.yaml")
MODELS = Path("src/mondo_source/datamodel.py")


def test_the_committed_models_are_what_the_schema_generates(monkeypatch):
    # The models record the schema's path as it was given, so it is given as make gives it.
    monkeypatch.chdir(ROOT)

    generated = PydanticGenerator(str(SCHEMA), importmap=importmap()).serialize()

    assert generated == MODELS.read_text(), "datamodel.py is out of date: run `make models`"
