"""YAML output that reads back the same under YAML 1.1 and YAML 1.2.

PyYAML quotes strings that YAML 1.1 would read as something else ("yes", "1:30"),
but not ones only YAML 1.2 would ("2E4" is a string in 1.1 and the float 20000.0
in 1.2). This adds the YAML 1.2 core-schema cases. yamlcore's CommonDumper is meant
to do the same, but fails in yamlcore 0.0.4.
"""

import re
from pathlib import Path

import yaml

YAML_12_NON_STRING = re.compile(
    r"""^(?:~|null|Null|NULL|true|True|TRUE|false|False|FALSE
    |[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+
    |[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?
    |[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$""",
    re.VERBOSE,
)


class Dumper(getattr(yaml, "CSafeDumper", yaml.SafeDumper)):
    pass


def _represent_str(dumper, value: str):
    style = "'" if YAML_12_NON_STRING.match(value) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


Dumper.add_representer(str, _represent_str)


def dump_yaml(data, path: Path):
    with open(path, "w") as f:
        yaml.dump(data, f, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=1000)


def load_yaml(path: Path):
    return yaml.load(Path(path).read_text(), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
