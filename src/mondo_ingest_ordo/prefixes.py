"""The release's prefix map: a curies extended prefix map, kept as YAML."""

from pathlib import Path

import curies
import yaml


def load_converter(path: Path) -> curies.Converter:
    return curies.Converter.from_extended_prefix_map(yaml.safe_load(Path(path).read_text()))
