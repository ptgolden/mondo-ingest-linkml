import pytest

from mondo_source.yamlio import dump_yaml, load_yaml

# Strings that YAML 1.2's core schema reads as a number, a boolean or null. PyYAML,
# which is YAML 1.1, leaves the first few unquoted by itself: "2E4" is a gene alias in
# ORDO, and a YAML 1.2 reader would make it 20000.0.
READ_AS_SOMETHING_ELSE = ["2E4", "1e3", "0o17", "0x1F", ".5", "12", "-3", "1.5", "true", "False", "null", "~", ".inf", ".NaN"]


@pytest.mark.parametrize("text", READ_AS_SOMETHING_ELSE)
def test_a_string_another_yaml_would_misread_is_quoted(tmp_path, text):
    path = tmp_path / "strings.yaml"

    dump_yaml({"value": text}, path)

    assert path.read_text() == f"value: '{text}'\n"
    assert load_yaml(path) == {"value": text}


def test_other_strings_and_other_types_are_written_plainly(tmp_path):
    path = tmp_path / "plain.yaml"

    dump_yaml({"label": "Leprosy", "deprecated": True, "count": 2}, path)

    assert path.read_text() == "label: Leprosy\ndeprecated: true\ncount: 2\n"
