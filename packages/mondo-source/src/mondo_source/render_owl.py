"""Render a SourceRelease as OWL with linkml-owl, from the `owl` annotations in the schema.

Three additions to linkml-owl's own CLI:
- the release's prefix map is added to the schema's prefixes, so the CURIEs in the
  data (Orphanet:, MONDO:, ...) expand;
- `owl.template`s get an `iri()` function that expands a CURIE to a full IRI. Templates
  can't emit every CURIE as is: OWL functional syntax rejects some local parts, such as
  ICD-10's dagger and asterisk codes (ICD10:A98.5+, ICD10:N08.0*);
- an ontology header (linkml-owl writes none): the component's ontology and version
  IRIs, and annotations from the release metadata (HEADER), on linkml-owl's
  py-horned-owl document;
- declarations for the annotation properties used. py-horned-owl writes none, and
  without them an OWL parser can't tell a SubAnnotationPropertyOf (synonym types,
  subsets) from an object property axiom.
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
from pyhornedowl import PyIndexedOntology
from pyhornedowl.model import (
    Annotation,
    AnnotationAssertion,
    AnnotationProperty,
    OntologyAnnotation,
    OntologyID,
    SimpleLiteral,
    SubAnnotationPropertyOf,
)

from mondo_source.prefixes import load_converter
from mondo_source.yamlio import load_yaml


# Ontology annotations from release metadata: (property, metadata slot, value is an IRI).
# A slot the release leaves empty gives no annotation. Values are written as the
# metadata file has them.
HEADER = [
    ("http://www.w3.org/2002/07/owl#versionInfo", "source_version", False),
    ("http://www.geneontology.org/formats/oboInOwl#source", "source_version_iri", True),
    ("http://purl.org/dc/terms/license", "source_license", True),
    ("http://purl.org/dc/terms/modified", "source_date", False),
    ("http://purl.org/pav/createdOn", "generated_at", False),
]

# OWL 2's built-in annotation properties, which are never declared.
BUILT_IN = {
    "http://www.w3.org/2000/01/rdf-schema#label",
    "http://www.w3.org/2000/01/rdf-schema#comment",
    "http://www.w3.org/2000/01/rdf-schema#seeAlso",
    "http://www.w3.org/2000/01/rdf-schema#isDefinedBy",
    "http://www.w3.org/2002/07/owl#deprecated",
    "http://www.w3.org/2002/07/owl#versionInfo",
    "http://www.w3.org/2002/07/owl#priorVersion",
    "http://www.w3.org/2002/07/owl#backwardCompatibleWith",
    "http://www.w3.org/2002/07/owl#incompatibleWith",
}


class Dumper(OWLDumper):
    def __init__(self, converter: curies.Converter, ontology_iri: str, version_iri: str, metadata: dict):
        super().__init__()
        self.converter = converter
        self.ontology_iri = ontology_iri
        self.version_iri = version_iri
        self.metadata = metadata

    def to_ontology_document(self, element, schema, iri=None):
        doc = super().to_ontology_document(element, schema, iri)
        doc.add_component(OntologyID(doc.iri(self.ontology_iri), doc.iri(self.version_iri)))
        used = set(annotation_properties(doc))
        for prop, slot, is_iri in HEADER:
            if (value := self.metadata.get(slot)) is not None:
                av = doc.iri(str(value)) if is_iri else SimpleLiteral(str(value))
                doc.add_component(OntologyAnnotation(Annotation(AnnotationProperty(doc.iri(prop)), av)))
                used.add(prop)
        for prop in sorted(used - BUILT_IN):
            doc.declare_annotation_property(doc.iri(prop))
        return doc

    def _element_to_template_dict(self, element, val=None):
        d = super()._element_to_template_dict(element, val)
        d["iri"] = lambda x: f"<{self.converter.expand_or_standardize(str(x), strict=True)}>"
        return d


def annotation_properties(doc: PyIndexedOntology):
    """IRIs of the annotation properties used in assertions, axiom annotations and
    SubAnnotationPropertyOf axioms."""
    for axiom in doc.get_axioms():
        c = axiom.component
        if isinstance(c, AnnotationAssertion):
            yield str(c.ann.ap.first)
        elif isinstance(c, SubAnnotationPropertyOf):
            yield str(c.sub.first)
            yield str(c.sup.first)
        yield from (str(a.ap.first) for a in axiom.ann)


def main(
    release: Annotated[Path, typer.Argument()],
    schema: Annotated[Path, typer.Option()],
    prefixes: Annotated[Path, typer.Option(help="Extended prefix map (YAML) the release's CURIEs use")],
    output: Annotated[Path, typer.Option(help="RDF/XML output")],
    metadata: Annotated[Path, typer.Option(help="The release's metadata (YAML), for the ontology header")],
    ontology_iri: Annotated[str, typer.Option()],
    version_iri: Annotated[str, typer.Option()],
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
    dumper = Dumper(converter, ontology_iri, version_iri, load_yaml(metadata))
    output.write_text(dumper.dumps(element, schemaview=sv, output_type="owl"))

