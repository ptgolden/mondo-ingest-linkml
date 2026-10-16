"""Render a SourceRelease as OWL with linkml-owl, from the `owl` annotations in the schema.

The ontology header is left to `robot annotate`: linkml-owl writes RDF/XML without one.

Two additions to linkml-owl's own CLI:
- the release's prefix map is added to the schema's prefixes, so the CURIEs in the
  data (Orphanet:, MONDO:, ...) expand;
- `owl.template`s get an `iri()` function that expands a CURIE to a full IRI. Templates
  can't emit every CURIE as is: OWL functional syntax rejects some local parts, such as
  ICD-10's dagger and asterisk codes (ICD10:A98.5+, ICD10:N08.0*).
"""

import json
from pathlib import Path
from typing import Annotated

import curies
import typer
from linkml.generators.pythongen import PythonGenerator
from linkml_owl.dumpers.owl_dumper import OWLDumper
from linkml_runtime.linkml_model.meta import Prefix
from linkml_runtime.loaders import yaml_loader
from linkml_runtime.utils.schemaview import SchemaView
from linkml_runtime.utils.yamlutils import YAMLRoot

from mondo_source.prefixes import load_converter


class Dumper(OWLDumper):
    def __init__(self, converter: curies.Converter):
        super().__init__()
        self.converter = converter

    def _element_to_template_dict(self, element, val=None):
        d = super()._element_to_template_dict(element, val)
        d["iri"] = lambda x: f"<{self.converter.expand_or_standardize(str(x), strict=True)}>"
        return d


def main(
    release: Annotated[Path, typer.Argument()],
    schema: Annotated[Path, typer.Option()],
    prefixes: Annotated[Path, typer.Option(help="Extended prefix map (YAML) the release's CURIEs use")],
    output: Annotated[Path, typer.Option(help="RDF/XML output")],
    importmap: Annotated[Path | None, typer.Option(help="LinkML importmap (JSON)")] = None,
):
    """Render a SourceRelease as OWL (RDF/XML)."""
    imports = json.loads(importmap.read_text()) if importmap else None
    datamodel = PythonGenerator(str(schema), importmap=imports).compile_module()
    element = yaml_loader.load(str(release), target_class=datamodel.SourceRelease)
    assert isinstance(element, YAMLRoot)
    converter = load_converter(prefixes)
    sv = SchemaView(str(schema), importmap=imports)
    assert sv.schema is not None and isinstance(sv.schema.prefixes, dict)
    for prefix, namespace in converter.bimap.items():
        sv.schema.prefixes[prefix] = Prefix(prefix, namespace)
    sv.set_modified()
    output.write_text(Dumper(converter).dumps(element, schemaview=sv, output_type="owl"))

