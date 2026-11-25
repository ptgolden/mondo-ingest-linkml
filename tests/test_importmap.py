from pathlib import Path

from mondo_source.importmap import importmap


def test_the_sssom_import_resolves_to_the_installed_schema():
    (directory,) = importmap().values()

    assert list(importmap()) == ["sssom_schema:"]
    assert directory.endswith("/")
    assert (Path(directory) / "sssom_schema.yaml").is_file()
