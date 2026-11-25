from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.12.0"
version = "0.7.0"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'mondo_source',
     'default_range': 'string',
     'description': "What Mondo takes in from one source: the source's in-scope "
                    "terms, with Mondo's interpretation of them already applied "
                    "(e.g. ORDO's part_of as parents, its synonyms as EXACT, "
                    'synonyms generated from labels). The OWL and SSSOM files a '
                    'source repo publishes are renderings of this.\n'
                    'EXPERIMENT: it ships with the mondo-source package, which '
                    'every source depends on. In the target architecture it may '
                    'instead live in mondo-ingest, fetched by PURL.\n'
                    "Design rules: (1) Data Mondo's interpretation creates, as "
                    'opposed to translates, says so: e.g. synonyms copied from '
                    'labels carry synonym_type mondo:GENERATED_FROM_LABEL. (2) No '
                    "overloaded fields. OBO's `xref` and `source` are split into a "
                    'mapping predicate, a mapping justification and a comment. (3) '
                    'Mappings are inlined on the term they are about, using the '
                    "sssom-schema package's own slots, so the SSSOM file is a "
                    'projection of this data, not a second source of truth.',
     'id': 'https://w3id.org/monarch-initiative/mondo-source/experimental',
     'imports': ['linkml:types', 'sssom_schema:sssom_schema'],
     'license': 'https://creativecommons.org/publicdomain/zero/1.0/',
     'name': 'mondo_source',
     'prefixes': {'IAO': {'prefix_prefix': 'IAO',
                          'prefix_reference': 'http://purl.obolibrary.org/obo/IAO_'},
                  'dcterms': {'prefix_prefix': 'dcterms',
                              'prefix_reference': 'http://purl.org/dc/terms/'},
                  'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'mondo_source': {'prefix_prefix': 'mondo_source',
                                   'prefix_reference': 'https://w3id.org/monarch-initiative/mondo-source/'},
                  'oboInOwl': {'prefix_prefix': 'oboInOwl',
                               'prefix_reference': 'http://www.geneontology.org/formats/oboInOwl#'},
                  'owl': {'prefix_prefix': 'owl',
                          'prefix_reference': 'http://www.w3.org/2002/07/owl#'},
                  'pav': {'prefix_prefix': 'pav',
                          'prefix_reference': 'http://purl.org/pav/'},
                  'rdf': {'prefix_prefix': 'rdf',
                          'prefix_reference': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'},
                  'rdfs': {'prefix_prefix': 'rdfs',
                           'prefix_reference': 'http://www.w3.org/2000/01/rdf-schema#'},
                  'skos': {'prefix_prefix': 'skos',
                           'prefix_reference': 'http://www.w3.org/2004/02/skos/core#'},
                  'sssom': {'prefix_prefix': 'sssom',
                            'prefix_reference': 'https://w3id.org/sssom/'},
                  'sssom_schema': {'prefix_prefix': 'sssom_schema',
                                   'prefix_reference': 'https://raw.githubusercontent.com/mapping-commons/sssom/v1.0.0/src/sssom_schema/schema/'}},
     'source_file': 'src/mondo_source/schema/mondo_source.yaml',
     'title': 'Mondo source schema (experimental draft)'} )

class EntityTypeEnum(str, Enum):
    owl_class = "owl class"
    owl_object_property = "owl object property"
    owl_data_property = "owl data property"
    owl_annotation_property = "owl annotation property"
    owl_named_individual = "owl named individual"
    skos_concept = "skos concept"
    rdfs_resource = "rdfs resource"
    rdfs_class = "rdfs class"
    rdfs_literal = "rdfs literal"
    """
    This value indicate that the entity being mapped is not a semantic entity with a distinct identifier, but is instead represented entirely by its literal label. This value MUST NOT be used in the predicate_type slot.
    """
    rdfs_datatype = "rdfs datatype"
    rdf_property = "rdf property"


class PredicateModifierEnum(str, Enum):
    Not = "Not"
    """
    Negating the mapping predicate. The meaning of the triple becomes subject_id is not a predicate_id match to object_id.
    """


class MappingCardinalityEnum(str, Enum):
    number_1COLON1 = "1:1"
    """
    One-to-one mapping
    """
    number_1COLONn = "1:n"
    """
    One-to-many mapping
    """
    nCOLON1 = "n:1"
    """
    Many-to-one mapping
    """
    number_1COLON0 = "1:0"
    """
    One-to-none mapping
    """
    number_0COLON1 = "0:1"
    """
    None-to-one mapping
    """
    nCOLONn = "n:n"
    """
    Many-to-many mapping
    """


class SynonymScope(str, Enum):
    EXACT = "EXACT"
    RELATED = "RELATED"
    BROAD = "BROAD"
    NARROW = "NARROW"



class MappingSet(ConfiguredBaseModel):
    """
    Represents a set of mappings
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sssom/schema/',
         'slot_usage': {'license': {'name': 'license', 'required': True}}})

    curie_map: Optional[dict[str, Union[str, Prefix]]] = Field(default=None, description="""A dictionary that contains prefixes as keys and their URI expansions as values.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set'],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/225',
                      'https://github.com/mapping-commons/sssom/pull/349',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/curie_map.sssom.tsv']} })
    mappings: Optional[list[Mapping]] = Field(default=None, description="""Contains a list of mapping objects""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'Term'], 'recommended': True} })
    mapping_set_id: str = Field(default=..., description="""A globally unique identifier for the mapping set (not each individual mapping). Should be IRI, ideally resolvable.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping set reference'],
         'examples': [{'description': '(A persistent URI pointing to the latest '
                                      'version of the Mondo - NCIT mapping in the '
                                      'Mondo namespace.)',
                       'value': 'http://purl.obolibrary.org/obo/mondo/mappings/mondo_exactmatch_ncit.sssom.tsv'}]} })
    mapping_set_version: Optional[str] = Field(default=None, description="""A version string for the mapping.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set'],
         'examples': [{'description': '(A date-based version that indicates that the '
                                      'mapping was published on the 1st January in '
                                      '2021.)',
                       'value': '2020-01-01'},
                      {'description': '(A semantic version tag that indicates that '
                                      'this is the 1st major, 2nd minor version, patch '
                                      '1 (https://semver.org/).)',
                       'value': '1.2.1'}],
         'slot_uri': 'owl:versionInfo'} })
    mapping_set_source: Optional[list[str]] = Field(default=None, description="""A mapping set or set of mapping set that was used to derive the mapping set.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set'],
         'examples': [{'description': 'A persistent, ideally versioned, link to the '
                                      'mapping set from which the current mapping set '
                                      'is derived.',
                       'value': 'http://purl.obolibrary.org/obo/mondo/mappings/2022-05-20/mondo_exactmatch_ncit.sssom.tsv'}],
         'slot_uri': 'prov:wasDerivedFrom'} })
    mapping_set_title: Optional[str] = Field(default=None, description="""The display name of a mapping set.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set'],
         'examples': [{'value': 'The Mondo-OMIM mappings by Monarch Initiative.'}],
         'slot_uri': 'dcterms:title'} })
    mapping_set_description: Optional[str] = Field(default=None, description="""A description of the mapping set.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set'],
         'examples': [{'value': 'This mapping set was produced to integrate human and '
                                'mouse phenotype data at the IMPC. It is primarily '
                                'used for making mouse phenotypes searchable by human '
                                'synonyms at https://mousephenotype.org/.'}],
         'slot_uri': 'dcterms:description'} })
    creator_id: Optional[list[str]] = Field(default=None, description="""Identifies the persons or groups responsible for the creation of the mapping. The creator is the agent that put the mapping in its published form, which may be different from the author, which is a person that was actively involved in the assertion of the mapping. Recommended to be a list of ORCIDs or otherwise identifying URIs.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'dcterms:creator'} })
    creator_label: Optional[list[str]] = Field(default=None, description="""A string identifying the creator of this mapping. In the spirit of provenance, consider using creator_id instead.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping']} })
    license: str = Field(default=..., description="""A url to the license of the mapping. In absence of a license we assume no license.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'dcterms:license'} })
    subject_type: Optional[EntityTypeEnum] = Field(default=None, description="""The type of entity that is being mapped.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'owl:Class'}],
         'instantiates': ['sssom:Propagatable']} })
    subject_source: Optional[str] = Field(default=None, description="""URI of vocabulary or identifier source for the subject.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': 'A persistent OBO CURIE pointing to the latest '
                                      'version of the Mondo ontology.',
                       'value': 'obo:mondo.owl'},
                      {'description': 'A Wikidata identifier for the Uberon ontology '
                                      'resource.',
                       'value': 'wikidata:Q7876491'}],
         'instantiates': ['sssom:Propagatable']} })
    subject_source_version: Optional[str] = Field(default=None, description="""Version IRI or version string of the source of the subject term.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': '(A persistent Version IRI pointing to the Mondo '
                                      "version '2021-01-30')",
                       'value': 'http://purl.obolibrary.org/obo/mondo/releases/2021-01-30/mondo.owl'}],
         'instantiates': ['sssom:Propagatable']} })
    object_type: Optional[EntityTypeEnum] = Field(default=None, description="""The type of entity that is being mapped.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'owl:Class'}],
         'instantiates': ['sssom:Propagatable']} })
    object_source: Optional[str] = Field(default=None, description="""URI of vocabulary or identifier source for the object.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': 'A persistent OBO CURIE pointing to the latest '
                                      'version of the Mondo ontology.',
                       'value': 'obo:mondo.owl'},
                      {'description': 'A Wikidata identifier for the Uberon ontology '
                                      'resource.',
                       'value': 'wikidata:Q7876491'}],
         'instantiates': ['sssom:Propagatable']} })
    object_source_version: Optional[str] = Field(default=None, description="""Version IRI or version string of the source of the object term.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': '(A persistent Version IRI pointing to the Mondo '
                                      "version '2021-01-30')",
                       'value': 'http://purl.obolibrary.org/obo/mondo/releases/2021-01-30/mondo.owl'}],
         'instantiates': ['sssom:Propagatable']} })
    mapping_provider: Optional[str] = Field(default=None, description="""URL pointing to the source that provided the mapping, for example an ontology that already contains the mappings, or a database from which it was derived.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable']} })
    mapping_tool: Optional[str] = Field(default=None, description="""A reference to the tool or algorithm that was used to generate the mapping. Should be a URL pointing to more info about it, but can be free text.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'https://github.com/AgreementMakerLight/AML-Project'}],
         'instantiates': ['sssom:Propagatable']} })
    mapping_tool_version: Optional[str] = Field(default=None, description="""Version string that denotes the version of the mapping tool used.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'v3.2'}],
         'instantiates': ['sssom:Propagatable']} })
    mapping_date: Optional[date] = Field(default=None, description="""The date the mapping was asserted. This is different from the date the mapping was published or compiled in a SSSOM file.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable'],
         'slot_uri': 'pav:authoredOn'} })
    publication_date: Optional[date] = Field(default=None, description="""The date the mapping was published. This is different from the date the mapping was asserted.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'dcterms:created'} })
    subject_match_field: Optional[list[str]] = Field(default=None, description="""A list of properties (term annotations on the subject) that was used for the match.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable']} })
    object_match_field: Optional[list[str]] = Field(default=None, description="""A list of properties (term annotations on the object) that was used for the match.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable']} })
    subject_preprocessing: Optional[list[str]] = Field(default=None, description="""Method of preprocessing applied to the fields of the subject. If different preprocessing steps were performed on different fields, it is recommended to store the match in separate rows.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'semapv:Stemming'},
                      {'value': 'semapv:StopWordRemoval'}],
         'instantiates': ['sssom:Propagatable']} })
    object_preprocessing: Optional[list[str]] = Field(default=None, description="""Method of preprocessing applied to the fields of the object. If different preprocessing steps were performed on different fields, it is recommended to store the match in separate rows.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'semapv:Stemming'},
                      {'value': 'semapv:StopWordRemoval'}],
         'instantiates': ['sssom:Propagatable']} })
    see_also: Optional[list[str]] = Field(default=None, description="""A URL specific for the mapping instance. E.g. for kboom we have a per-mapping image that shows surrounding axioms that drive probability. Could also be a github issue URL that discussed a complicated alignment""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'rdfs:seeAlso'} })
    issue_tracker: Optional[str] = Field(default=None, description="""A URL location of the issue tracker for this entity.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping registry'],
         'examples': [{'description': '(A URL resolving to the issue tracker of the '
                                      'Mouse-Human mapping initiative)',
                       'value': 'https://github.com/mapping-commons/mh_mapping_initiative/issues'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/78',
                      'https://github.com/mapping-commons/sssom/pull/259',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/issue_tracker.sssom.tsv']} })
    other: Optional[str] = Field(default=None, description="""Pipe separated list of key value pairs for properties not part of the SSSOM spec. Can be used to encode additional provenance data.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping']} })
    comment: Optional[str] = Field(default=None, description="""Free text field containing either curator notes or text generated by tool providing additional informative information.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'rdfs:comment'} })
    extension_definitions: Optional[list[ExtensionDefinition]] = Field(default=None, description="""A list that defines the extension slots used in the mapping set.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set'],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/328',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/extension-slots.sssom.tsv']} })


class Mapping(ConfiguredBaseModel):
    """
    Represents an individual mapping between a pair of entities
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'owl:Axiom',
         'from_schema': 'https://w3id.org/sssom/schema/',
         'rules': [{'postconditions': {'slot_conditions': {'subject_label': {'name': 'subject_label',
                                                                             'required': True}}},
                    'preconditions': {'slot_conditions': {'subject_type': {'equals_string': 'rdfs '
                                                                                            'literal',
                                                                           'name': 'subject_type'}}}},
                   {'postconditions': {'slot_conditions': {'subject_id': {'name': 'subject_id',
                                                                          'required': True}}},
                    'preconditions': {'slot_conditions': {'subject_type': {'name': 'subject_type',
                                                                           'none_of': [{'equals_string': 'rdfs '
                                                                                                         'literal'}]}}}},
                   {'postconditions': {'slot_conditions': {'object_label': {'name': 'object_label',
                                                                            'required': True}}},
                    'preconditions': {'slot_conditions': {'object_type': {'equals_string': 'rdfs '
                                                                                           'literal',
                                                                          'name': 'object_type'}}}},
                   {'postconditions': {'slot_conditions': {'object_id': {'name': 'object_id',
                                                                         'required': True}}},
                    'preconditions': {'slot_conditions': {'object_type': {'name': 'object_type',
                                                                          'none_of': [{'equals_string': 'rdfs '
                                                                                                        'literal'}]}}}}]})

    subject_id: Optional[str] = Field(default=None, description="""The ID of the subject of the mapping.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping'],
         'examples': [{'description': 'The CURIE denoting the Human Phenotype Ontology '
                                      "concept of 'Thickened ears'",
                       'value': 'HP:0009894'}],
         'mappings': ['owl:annotatedSource'],
         'slot_uri': 'owl:annotatedSource'} })
    subject_label: Optional[str] = Field(default=None, description="""The label of subject of the mapping""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping'],
         'examples': [{'value': 'Thickened ears'}],
         'recommended': True} })
    subject_category: Optional[str] = Field(default=None, description="""The conceptual category to which the subject belongs to. This can be a string denoting the category or a term from a controlled vocabulary. This slot is deliberately underspecified. Conceptual categories can range from those that are found in general upper ontologies such as BFO (e.g. process, temporal region, etc) to those that serve as upper ontologies in specific domains, such as COB or BioLink (e.g. gene, disease, chemical entity). The purpose of this optional field is documentation for human reviewers - when a category is known and documented clearly, the cost of interpreting and evaluating the mapping decreases.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': '(The CURIE of the Uberon term for "anatomical '
                                      'entity".)',
                       'value': 'UBERON:0001062'},
                      {'description': '(A string, rather than ID, describing the '
                                      '"anatomical entity" category. This is possible, '
                                      'but less preferred than using an ID.)',
                       'value': 'anatomical entity'},
                      {'description': '(The CURIE of the biolink class for genes.)',
                       'value': 'biolink:Gene'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/13',
                      'https://github.com/mapping-commons/sssom/issues/256']} })
    predicate_id: str = Field(default=..., description="""The ID of the predicate or relation that relates the subject and object of this match.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': 'The subject and the object are instances (owl '
                                      'individuals), and the two instances are the '
                                      'same.',
                       'value': 'owl:sameAs'},
                      {'description': 'The subject and the object are classes (owl '
                                      'class), and the two classes are the same.',
                       'value': 'owl:equivalentClass'},
                      {'description': 'The subject and the object are properties (owl '
                                      'object, data, annotation properties), and the '
                                      'two properties are the same.',
                       'value': 'owl:equivalentProperty'},
                      {'description': 'The subject and the object are classes (owl '
                                      'class), and the subject is a subclass of the '
                                      'object.',
                       'value': 'rdfs:subClassOf'},
                      {'description': 'The subject and the object are properties (owl '
                                      'object, data, annotation properties), and the '
                                      'subject is a subproperty of the object.',
                       'value': 'rdfs:subPropertyOf'},
                      {'description': 'The subject and the object are associated in '
                                      'some unspecified way.',
                       'value': 'skos:relatedMatch'},
                      {'description': 'The subject and the object are sufficiently '
                                      'similar that they can be used interchangeably '
                                      'in some information retrieval applications.',
                       'value': 'skos:closeMatch'},
                      {'description': 'The subject and the object can, with a high '
                                      'degree of confidence, be used interchangeably '
                                      'across a wide range of information retrieval '
                                      'applications.',
                       'value': 'skos:exactMatch'},
                      {'description': 'From the SKOS primer: A triple skos:narrower '
                                      '(and skos:narrowMatch) asserts that , the '
                                      'object of the triple, is a narrower concept '
                                      'than , the subject of the triple.',
                       'value': 'skos:narrowMatch'},
                      {'description': 'From the SKOS primer: A triple skos:broader '
                                      '(and skos:broadMatch) asserts that , the object '
                                      'of the triple, is a broader concept than , the '
                                      'subject of the triple.',
                       'value': 'skos:broadMatch'},
                      {'description': 'Two terms are related in some way. The meaning '
                                      'is frequently consistent across a single set of '
                                      'mappings. Note this property is often '
                                      'overloaded even where the terms are of a '
                                      'different nature (e.g. interpro2go)',
                       'value': 'oboInOwl:hasDbXref'},
                      {'description': 'The subject and the object are associated in '
                                      'some unspecified way. The object IRI often '
                                      'resolves to a resource on the web that provides '
                                      'additional information.',
                       'value': 'rdfs:seeAlso'}],
         'mappings': ['owl:annotatedProperty'],
         'slot_uri': 'owl:annotatedProperty'} })
    predicate_label: Optional[str] = Field(default=None, description="""The label of the predicate/relation of the mapping""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': 'The label of the oboInOwl:hasDbXref property to '
                                      'represent cross-references.',
                       'value': 'has cross-reference'}]} })
    predicate_modifier: Optional[PredicateModifierEnum] = Field(default=None, description="""A modifier for negating the predicate. See https://github.com/mapping-commons/sssom/issues/40 for discussion""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': 'Negates the predicate, see documentation of '
                                      'predicate_modifier_enum',
                       'value': 'Not'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/107']} })
    object_id: Optional[str] = Field(default=None, description="""The ID of the object of the mapping.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': 'The CURIE denoting the Human Phenotype Ontology '
                                      "concept of 'Thickened ears'",
                       'value': 'HP:0009894'}],
         'mappings': ['owl:annotatedTarget'],
         'slot_uri': 'owl:annotatedTarget'} })
    object_label: Optional[str] = Field(default=None, description="""The label of object of the mapping""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'value': 'Thickened ears'}],
         'recommended': True} })
    object_category: Optional[str] = Field(default=None, description="""The conceptual category to which the subject belongs to. This can be a string denoting the category or a term from a controlled vocabulary. This slot is deliberately underspecified. Conceptual categories can range from those that are found in general upper ontologies such as BFO (e.g. process, temporal region, etc) to those that serve as upper ontologies in specific domains, such as COB or BioLink (e.g. gene, disease, chemical entity). The purpose of this optional field is documentation for human reviewers - when a category is known and documented clearly, the cost of interpreting and evaluating the mapping decreases.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': '(The CURIE of the Uberon term for "anatomical '
                                      'entity".)',
                       'value': 'UBERON:0001062'},
                      {'description': '(A string, rather than ID, describing the '
                                      '"anatomical entity" category. This is possible, '
                                      'but less preferred than using an ID.)',
                       'value': 'anatomical entity'},
                      {'description': '(The CURIE of the biolink class for genes.)',
                       'value': 'biolink:Gene'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/13',
                      'https://github.com/mapping-commons/sssom/issues/256']} })
    mapping_justification: str = Field(default=..., description="""A mapping justification is an action (or the written representation of that action) of showing a mapping to be right or reasonable.""", json_schema_extra = { "linkml_meta": {'any_of': [{'equals_string': 'semapv:LexicalMatching'},
                    {'equals_string': 'semapv:LogicalReasoning'},
                    {'equals_string': 'semapv:CompositeMatching'},
                    {'equals_string': 'semapv:UnspecifiedMatching'},
                    {'equals_string': 'semapv:SemanticSimilarityThresholdMatching'},
                    {'equals_string': 'semapv:LexicalSimilarityThresholdMatching'},
                    {'equals_string': 'semapv:MappingChaining'},
                    {'equals_string': 'semapv:MappingReview'},
                    {'equals_string': 'semapv:ManualMappingCuration'}],
         'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'value': 'semapv:LexicalMatching'},
                      {'value': 'semapv:ManualMappingCuration'}]} })
    author_id: Optional[list[str]] = Field(default=None, description="""Identifies the persons or groups responsible for asserting the mappings. Recommended to be a list of ORCIDs or otherwise identifying URIs.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'], 'slot_uri': 'pav:authoredBy'} })
    author_label: Optional[list[str]] = Field(default=None, description="""A string identifying the author of this mapping. In the spirit of provenance, consider using author_id instead.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    reviewer_id: Optional[list[str]] = Field(default=None, description="""Identifies the persons or groups that reviewed and confirmed the mapping. Recommended to be a list of ORCIDs or otherwise identifying URIs.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    reviewer_label: Optional[list[str]] = Field(default=None, description="""A string identifying the reviewer of this mapping. In the spirit of provenance, consider using reviewer_id instead.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    creator_id: Optional[list[str]] = Field(default=None, description="""Identifies the persons or groups responsible for the creation of the mapping. The creator is the agent that put the mapping in its published form, which may be different from the author, which is a person that was actively involved in the assertion of the mapping. Recommended to be a list of ORCIDs or otherwise identifying URIs.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'dcterms:creator'} })
    creator_label: Optional[list[str]] = Field(default=None, description="""A string identifying the creator of this mapping. In the spirit of provenance, consider using creator_id instead.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping']} })
    license: Optional[str] = Field(default=None, description="""A url to the license of the mapping. In absence of a license we assume no license.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'dcterms:license'} })
    subject_type: Optional[EntityTypeEnum] = Field(default=None, description="""The type of entity that is being mapped.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'owl:Class'}],
         'instantiates': ['sssom:Propagatable']} })
    subject_source: Optional[str] = Field(default=None, description="""URI of vocabulary or identifier source for the subject.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': 'A persistent OBO CURIE pointing to the latest '
                                      'version of the Mondo ontology.',
                       'value': 'obo:mondo.owl'},
                      {'description': 'A Wikidata identifier for the Uberon ontology '
                                      'resource.',
                       'value': 'wikidata:Q7876491'}],
         'instantiates': ['sssom:Propagatable']} })
    subject_source_version: Optional[str] = Field(default=None, description="""Version IRI or version string of the source of the subject term.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': '(A persistent Version IRI pointing to the Mondo '
                                      "version '2021-01-30')",
                       'value': 'http://purl.obolibrary.org/obo/mondo/releases/2021-01-30/mondo.owl'}],
         'instantiates': ['sssom:Propagatable']} })
    object_type: Optional[EntityTypeEnum] = Field(default=None, description="""The type of entity that is being mapped.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'owl:Class'}],
         'instantiates': ['sssom:Propagatable']} })
    object_source: Optional[str] = Field(default=None, description="""URI of vocabulary or identifier source for the object.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': 'A persistent OBO CURIE pointing to the latest '
                                      'version of the Mondo ontology.',
                       'value': 'obo:mondo.owl'},
                      {'description': 'A Wikidata identifier for the Uberon ontology '
                                      'resource.',
                       'value': 'wikidata:Q7876491'}],
         'instantiates': ['sssom:Propagatable']} })
    object_source_version: Optional[str] = Field(default=None, description="""Version IRI or version string of the source of the object term.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': '(A persistent Version IRI pointing to the Mondo '
                                      "version '2021-01-30')",
                       'value': 'http://purl.obolibrary.org/obo/mondo/releases/2021-01-30/mondo.owl'}],
         'instantiates': ['sssom:Propagatable']} })
    mapping_provider: Optional[str] = Field(default=None, description="""URL pointing to the source that provided the mapping, for example an ontology that already contains the mappings, or a database from which it was derived.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable']} })
    mapping_source: Optional[str] = Field(default=None, description="""The mapping set this mapping was originally defined in. mapping_source is used for example when merging multiple mapping sets or deriving one mapping set from another.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'value': 'MONDO_MAPPINGS:mondo_exactmatch_ncit.sssom.tsv'}]} })
    mapping_cardinality: Optional[MappingCardinalityEnum] = Field(default=None, description="""A string indicating whether this mapping is from a 1:1 (the subject_id maps to a single object_id), 1:n (the subject maps to more than one object_id), n:1, 1:0, 0:1 or n:n group. Note that this is a convenience field that should be derivable from the mapping set.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    mapping_tool: Optional[str] = Field(default=None, description="""A reference to the tool or algorithm that was used to generate the mapping. Should be a URL pointing to more info about it, but can be free text.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'https://github.com/AgreementMakerLight/AML-Project'}],
         'instantiates': ['sssom:Propagatable']} })
    mapping_tool_version: Optional[str] = Field(default=None, description="""Version string that denotes the version of the mapping tool used.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'v3.2'}],
         'instantiates': ['sssom:Propagatable']} })
    mapping_date: Optional[date] = Field(default=None, description="""The date the mapping was asserted. This is different from the date the mapping was published or compiled in a SSSOM file.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable'],
         'slot_uri': 'pav:authoredOn'} })
    publication_date: Optional[date] = Field(default=None, description="""The date the mapping was published. This is different from the date the mapping was asserted.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'dcterms:created'} })
    confidence: Optional[float] = Field(default=None, description="""A score between 0 and 1 to denote the confidence or probability that the match is correct, where 1 denotes total confidence.""", ge=0.0, le=1.0, json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    curation_rule: Optional[list[str]] = Field(default=None, description="""A curation rule is a (potentially) complex condition executed by an agent that led to the establishment of a mapping. Curation rules often involve complex domain-specific considerations, which are hard to capture in an automated fashion. The curation rule is captured as a resource rather than a string, which enables higher levels of transparency and sharing across mapping sets. The URI representation of the curation rule is expected to be a resolvable identifier which provides details about the nature of the curation rule.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/166',
                      'https://github.com/mapping-commons/sssom/pull/258',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/curation_rule.sssom.tsv']} })
    curation_rule_text: Optional[list[str]] = Field(default=None, description="""A curation rule is a (potentially) complex condition executed by an agent that led to the establishment of a mapping. Curation rules often involve complex domain-specific considerations, which are hard to capture in an automated fashion. The curation rule should be captured as a resource (entity reference) rather than a string (see curation_rule element), which enables higher levels of transparency and sharing across mapping sets. The textual representation of curation rule is intended to be used in cases where (1) the creation of a resource is not practical from the perspective of the mapping_provider and (2) as an additional piece of metadata to augment the curation_rule element with a human readable text.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/166',
                      'https://github.com/mapping-commons/sssom/pull/258',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/curation_rule_text.sssom.tsv']} })
    subject_match_field: Optional[list[str]] = Field(default=None, description="""A list of properties (term annotations on the subject) that was used for the match.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable']} })
    object_match_field: Optional[list[str]] = Field(default=None, description="""A list of properties (term annotations on the object) that was used for the match.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable']} })
    match_string: Optional[list[str]] = Field(default=None, description="""String that is shared by subj/obj. It is recommended to indicate the fields for the match using the object and subject_match_field slots.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    subject_preprocessing: Optional[list[str]] = Field(default=None, description="""Method of preprocessing applied to the fields of the subject. If different preprocessing steps were performed on different fields, it is recommended to store the match in separate rows.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'semapv:Stemming'},
                      {'value': 'semapv:StopWordRemoval'}],
         'instantiates': ['sssom:Propagatable']} })
    object_preprocessing: Optional[list[str]] = Field(default=None, description="""Method of preprocessing applied to the fields of the object. If different preprocessing steps were performed on different fields, it is recommended to store the match in separate rows.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'semapv:Stemming'},
                      {'value': 'semapv:StopWordRemoval'}],
         'instantiates': ['sssom:Propagatable']} })
    similarity_score: Optional[float] = Field(default=None, description="""A score between 0 and 1 to denote the similarity between two entities, where 1 denotes equivalence, and 0 denotes disjointness. The score is meant to be used in conjunction with the similarity_measure field, to document, for example, the lexical or semantic match of a matching algorithm.""", ge=0.0, le=1.0, json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/385',
                      'https://github.com/mapping-commons/sssom/pull/386',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/similarity_score.sssom.tsv']} })
    similarity_measure: Optional[str] = Field(default=None, description="""The measure used for computing a similarity score. This field is meant to be used in conjunction with the similarity_score field, to document, for example, the lexical or semantic match of a matching algorithm. To make processing this field as unambiguous as possible, we recommend using wikidata CURIEs, but the type of this field is deliberately unspecified.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': '(the Wikidata IRI for the Jaccard index '
                                      'measure).',
                       'value': 'https://www.wikidata.org/entity/Q865360'},
                      {'description': '(the Wikidata CURIE for the Jaccard index '
                                      'measure).',
                       'value': 'wikidata:Q865360'},
                      {'description': '(a score to measure the distance between two '
                                      'character sequences).',
                       'value': 'Levenshtein distance'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/385',
                      'https://github.com/mapping-commons/sssom/pull/386',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/similarity_score.sssom.tsv']} })
    see_also: Optional[list[str]] = Field(default=None, description="""A URL specific for the mapping instance. E.g. for kboom we have a per-mapping image that shows surrounding axioms that drive probability. Could also be a github issue URL that discussed a complicated alignment""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'rdfs:seeAlso'} })
    issue_tracker_item: Optional[str] = Field(default=None, description="""The issue tracker item discussing this mapping.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': '(A URL resolving to an issue discussing a new '
                                      'SSSOM element request)',
                       'value': 'SSSOM_GITHUB_ISSUE:166'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/78',
                      'https://github.com/mapping-commons/sssom/pull/259',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/issue_tracker_item.sssom.tsv']} })
    other: Optional[str] = Field(default=None, description="""Pipe separated list of key value pairs for properties not part of the SSSOM spec. Can be used to encode additional provenance data.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping']} })
    comment: Optional[str] = Field(default=None, description="""Free text field containing either curator notes or text generated by tool providing additional informative information.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'rdfs:comment'} })

    @field_validator('mapping_justification')
    def pattern_mapping_justification(cls, v):
        pattern=re.compile(r"^semapv:(MappingReview|ManualMappingCuration|LogicalReasoning|LexicalMatching|CompositeMatching|UnspecifiedMatching|SemanticSimilarityThresholdMatching|LexicalSimilarityThresholdMatching|MappingChaining)$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid mapping_justification format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid mapping_justification format: {v}"
            raise ValueError(err_msg)
        return v


class MappingRegistry(ConfiguredBaseModel):
    """
    A registry for managing mapping sets. It holds a set of mapping set references, and can import other registries.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sssom/schema/'})

    mapping_registry_id: str = Field(default=..., description="""The unique identifier of a mapping registry.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping registry']} })
    mapping_registry_title: Optional[str] = Field(default=None, description="""The title of a mapping registry.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping registry']} })
    mapping_registry_description: Optional[str] = Field(default=None, description="""The description of a mapping registry.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping registry']} })
    imports: Optional[list[str]] = Field(default=None, description="""A list of registries that should be imported into this one.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping registry']} })
    mapping_set_references: Optional[list[MappingSetReference]] = Field(default=None, description="""A list of mapping set references.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping registry'], 'recommended': True} })
    documentation: Optional[str] = Field(default=None, description="""A URL to the documentation of this mapping commons.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping registry']} })
    homepage: Optional[str] = Field(default=None, description="""A URL to a homepage of this mapping commons.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping registry']} })
    issue_tracker: Optional[str] = Field(default=None, description="""A URL location of the issue tracker for this entity.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping registry'],
         'examples': [{'description': '(A URL resolving to the issue tracker of the '
                                      'Mouse-Human mapping initiative)',
                       'value': 'https://github.com/mapping-commons/mh_mapping_initiative/issues'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/78',
                      'https://github.com/mapping-commons/sssom/pull/259',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/issue_tracker.sssom.tsv']} })


class MappingSetReference(ConfiguredBaseModel):
    """
    A reference to a mapping set. It allows to augment mapping set metadata from the perspective of the registry, for example, providing confidence, or a local filename or a grouping.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sssom/schema/'})

    mapping_set_id: str = Field(default=..., description="""A globally unique identifier for the mapping set (not each individual mapping). Should be IRI, ideally resolvable.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping set reference'],
         'examples': [{'description': '(A persistent URI pointing to the latest '
                                      'version of the Mondo - NCIT mapping in the '
                                      'Mondo namespace.)',
                       'value': 'http://purl.obolibrary.org/obo/mondo/mappings/mondo_exactmatch_ncit.sssom.tsv'}]} })
    mirror_from: Optional[str] = Field(default=None, description="""A URL location from which to obtain a resource, such as a mapping set.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set reference']} })
    registry_confidence: Optional[float] = Field(default=None, description="""This value is set by the registry that indexes the mapping set. It reflects the confidence the registry has in the correctness of the mappings in the mapping set.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set reference']} })
    mapping_set_group: Optional[str] = Field(default=None, description="""Set by the owners of the mapping registry. A way to group .""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set reference']} })
    last_updated: Optional[date] = Field(default=None, description="""The date this reference was last updated.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set reference']} })
    local_name: Optional[str] = Field(default=None, description="""The local name assigned to file that corresponds to the downloaded mapping set.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set reference']} })


class Prefix(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sssom/schema/'})

    prefix_name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['prefix']} })
    prefix_url: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['prefix']} })


class ExtensionDefinition(ConfiguredBaseModel):
    """
    A definition of an extension (non-standard) slot.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sssom/schema/'})

    slot_name: str = Field(default=..., description="""The name of the extension slot.""", json_schema_extra = { "linkml_meta": {'domain_of': ['extension definition']} })
    property: Optional[str] = Field(default=None, description="""The property associated with the extension slot. It is intended to provide a non-ambiguous meaning to the slot (contrary to the slot_name, which for brevity reasons may be ambiguous).""", json_schema_extra = { "linkml_meta": {'domain_of': ['extension definition']} })
    type_hint: Optional[str] = Field(default=None, description="""Expected type of the values of the extension slot.""", json_schema_extra = { "linkml_meta": {'domain_of': ['extension definition']} })


class Propagatable(ConfiguredBaseModel):
    """
    Metamodel extension class to describe slots whose value can be propagated down from the MappingSet class to the Mapping class.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'sssom:Propagatable',
         'from_schema': 'https://w3id.org/sssom/schema/',
         'see_also': ['https://github.com/mapping-commons/sssom/issues/305']})

    propagated: Optional[bool] = Field(default=None, description="""Indicates whether a slot can be propagated from a mapping down to individual mappings.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Propagatable']} })


class NoTermFound(ConfiguredBaseModel):
    """
    sssom:NoTermFound can be used in place of a subject_id or object_id when the corresponding entity could not be found. It SHOULD be used in conjuction with a corresponding subject_source or object_source to signify where the term was not found.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'sssom:NoTermFound',
         'from_schema': 'https://w3id.org/sssom/schema/',
         'see_also': ['https://github.com/mapping-commons/sssom/issues/28',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/no_term_found.sssom.tsv']})

    pass


class SourceRelease(ConfiguredBaseModel):
    """
    One release of one source.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/monarch-initiative/mondo-source/experimental',
         'tree_root': True})

    metadata: ReleaseMetadata = Field(default=..., json_schema_extra = { "linkml_meta": {'annotations': {'owl.ignore': {'tag': 'owl.ignore', 'value': True}},
         'domain_of': ['SourceRelease']} })
    terms: list[Term] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['SourceRelease']} })


class ReleaseMetadata(ConfiguredBaseModel):
    """
    Freshness contract. mondo-ingest fails the build if schema_version does not match the schema it runs against, or if the release is older than it allows.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/monarch-initiative/mondo-source/experimental'})

    source_id: str = Field(default=..., description="""Short identifier for the source, e.g. \"ordo\".""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReleaseMetadata']} })
    source_version: str = Field(default=..., description="""The version string the source itself publishes.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReleaseMetadata'], 'slot_uri': 'pav:version'} })
    source_version_iri: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['ReleaseMetadata'], 'slot_uri': 'owl:versionIRI'} })
    source_date: Optional[str] = Field(default=None, description="""The release/modification date the source itself publishes, verbatim. Not typed as datetime because sources publish dates without timezones (ORDO: \"2026-06-26T16:36:02\"), which are not valid RFC 3339 date-times.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReleaseMetadata'], 'slot_uri': 'dcterms:modified'} })
    source_license: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['ReleaseMetadata'], 'slot_uri': 'dcterms:license'} })
    source_download_urls: Optional[list[str]] = Field(default=None, description="""The URLs this release was actually built from: one for a source that is a single file, several for one put together from several. Left out for a source whose URLs can't be published: OMIM's contain its download key.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReleaseMetadata']} })
    schema_version: str = Field(default=..., description="""Version of this schema the release was validated against.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReleaseMetadata']} })
    generated_at: datetime  = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['ReleaseMetadata']} })
    generated_by: str = Field(default=..., description="""Pipeline identity, e.g. repo URL and commit.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ReleaseMetadata']} })


class Term(ConfiguredBaseModel):
    """
    A class/concept in the source, identified by its CURIE in Mondo's prefix space.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'owl': {'tag': 'owl', 'value': 'Class'}},
         'from_schema': 'https://w3id.org/monarch-initiative/mondo-source/experimental'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Term']} })
    label: Optional[str] = Field(default=None, description="""The term's name in the source. Every term has one unless it is deprecated. A source can keep an identifier it has retired without saying what it was called (OMIM's moved entries, OncoTree's precursor codes), and then there is nothing to take the name from. Mondo keeps its own merged terms the same way (monarch-initiative/mondo#889). The condition is checked when a release is built, not by this schema.""", json_schema_extra = { "linkml_meta": {'annotations': {'owl': {'tag': 'owl', 'value': 'AnnotationAssertion'}},
         'domain_of': ['Term'],
         'slot_uri': 'rdfs:label'} })
    definition: Optional[str] = Field(default=None, description="""Textual definition.""", json_schema_extra = { "linkml_meta": {'annotations': {'owl': {'tag': 'owl', 'value': 'AnnotationAssertion'}},
         'domain_of': ['Term'],
         'slot_uri': 'IAO:0000115'} })
    synonyms: Optional[list[Synonym]] = Field(default=None, json_schema_extra = { "linkml_meta": {'annotations': {'owl.template': {'tag': 'owl.template',
                                          'value': '{% for s in synonyms %}\n'
                                                   'AnnotationAssertion(\n'
                                                   '  {% if s.synonym_type %}\n'
                                                   '  '
                                                   'Annotation(oboInOwl:hasSynonymType '
                                                   '{{ iri(s.synonym_type) }})\n'
                                                   '  {% endif %}\n'
                                                   '  {{ iri(s.scope.meaning) }} {{ '
                                                   'iri(id) }} {{ literal(s.text) }}\n'
                                                   ')\n'
                                                   '{% if s.synonym_type %}\n'
                                                   'SubAnnotationPropertyOf({{ '
                                                   'iri(s.synonym_type) }} '
                                                   'oboInOwl:SynonymTypeProperty)\n'
                                                   '{% endif %}\n'
                                                   '{% endfor %}'}},
         'domain_of': ['Term']} })
    parents: Optional[list[str]] = Field(default=None, description="""Direct parents, as Mondo reads the source's hierarchy (for ORDO: its rdfs:subClassOf parents plus its part_of targets).""", json_schema_extra = { "linkml_meta": {'annotations': {'owl': {'tag': 'owl', 'value': 'SubClassOf'}},
         'domain_of': ['Term'],
         'slot_uri': 'rdfs:subClassOf'} })
    relationships: Optional[list[Relationship]] = Field(default=None, description="""Existential relations (subClassOf R some T), e.g. disease to gene.""", json_schema_extra = { "linkml_meta": {'annotations': {'owl.template': {'tag': 'owl.template',
                                          'value': '{% for r in relationships %}\n'
                                                   'SubClassOf({{ iri(id) }} '
                                                   'ObjectSomeValuesFrom({{ '
                                                   'iri(r.predicate) }} {{ '
                                                   'iri(r.target) }}))\n'
                                                   '{% endfor %}'}},
         'domain_of': ['Term']} })
    deprecated: Optional[bool] = Field(default=None, json_schema_extra = { "linkml_meta": {'annotations': {'owl': {'tag': 'owl', 'value': 'AnnotationAssertion'}},
         'domain_of': ['Term'],
         'slot_uri': 'owl:deprecated'} })
    replaced_by: Optional[str] = Field(default=None, description="""The single term the source says replaces this one.""", json_schema_extra = { "linkml_meta": {'annotations': {'owl': {'tag': 'owl', 'value': 'AnnotationAssertion'}},
         'domain_of': ['Term'],
         'slot_uri': 'IAO:0100001'} })
    consider: Optional[list[str]] = Field(default=None, description="""Terms the source suggests instead, without claiming replacement.""", json_schema_extra = { "linkml_meta": {'annotations': {'owl': {'tag': 'owl', 'value': 'AnnotationAssertion'}},
         'domain_of': ['Term'],
         'slot_uri': 'oboInOwl:consider'} })
    subsets: Optional[list[str]] = Field(default=None, description="""Subsets the term belongs to, e.g. mondo_vocab:ordo_disorder.""", json_schema_extra = { "linkml_meta": {'annotations': {'owl.template': {'tag': 'owl.template',
                                          'value': '{% for s in subsets %}\n'
                                                   'AnnotationAssertion(oboInOwl:inSubset '
                                                   '{{ iri(id) }} {{ iri(s) }})\n'
                                                   '{% endfor %}'}},
         'domain_of': ['Term'],
         'slot_uri': 'oboInOwl:inSubset'} })
    mappings: Optional[list[TermMapping]] = Field(default=None, description="""Every mapping the source asserts from this term.""", json_schema_extra = { "linkml_meta": {'annotations': {'owl.template': {'tag': 'owl.template',
                                          'value': '{% for m in mappings %}\n'
                                                   '{% set is_xref = m.predicate_id == '
                                                   "'oboInOwl:hasDbXref' %}\n"
                                                   'AnnotationAssertion(\n'
                                                   '  '
                                                   'Annotation(sssom:mapping_justification '
                                                   '{{ iri(m.mapping_justification) '
                                                   '}})\n'
                                                   '  {% if m.comment %}\n'
                                                   '  Annotation(rdfs:comment {{ '
                                                   'literal(m.comment) }})\n'
                                                   '  {% endif %}\n'
                                                   '  {{ iri(m.predicate_id) }} {{ '
                                                   'iri(id) }}\n'
                                                   '  {{ literal(m.object_id) if '
                                                   'is_xref else iri(m.object_id) }}\n'
                                                   ')\n'
                                                   '{% endfor %}'}},
         'domain_of': ['mapping set', 'Term']} })

    @field_validator('id')
    def pattern_id(cls, v):
        pattern=re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:\S+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid id format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid id format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('subsets')
    def pattern_subsets(cls, v):
        pattern=re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:\S+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid subsets format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid subsets format: {v}"
            raise ValueError(err_msg)
        return v


class Synonym(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/monarch-initiative/mondo-source/experimental'})

    text: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Synonym']} })
    scope: SynonymScope = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Synonym']} })
    synonym_type: Optional[str] = Field(default=None, description="""A synonym type CURIE (e.g. ABBREVIATION), if the source states one.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Synonym'], 'slot_uri': 'oboInOwl:hasSynonymType'} })

    @field_validator('synonym_type')
    def pattern_synonym_type(cls, v):
        pattern=re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:\S+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid synonym_type format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid synonym_type format: {v}"
            raise ValueError(err_msg)
        return v


class Relationship(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/monarch-initiative/mondo-source/experimental'})

    predicate: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Relationship']} })
    target: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Relationship']} })

    @field_validator('predicate')
    def pattern_predicate(cls, v):
        pattern=re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:\S+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid predicate format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid predicate format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('target')
    def pattern_target(cls, v):
        pattern=re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:\S+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid target format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid target format: {v}"
            raise ValueError(err_msg)
        return v


class TermMapping(ConfiguredBaseModel):
    """
    An SSSOM mapping whose subject is the term it sits under. Uses the sssom-schema package's slots (so ranges, URIs and descriptions are SSSOM's) but not its `mapping` class, because that class's rules require subject_id, which here would only repeat the enclosing term's id. The SSSOM projection fills in subject_id and subject_label, and the projected file is validated as SSSOM.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/monarch-initiative/mondo-source/experimental',
         'slot_usage': {'object_id': {'name': 'object_id',
                                      'pattern': '^[A-Za-z_][A-Za-z0-9_.-]*:\\S+$',
                                      'required': True},
                        'predicate_id': {'name': 'predicate_id',
                                         'pattern': '^[A-Za-z_][A-Za-z0-9_.-]*:\\S+$'}}})

    subject_category: Optional[str] = Field(default=None, description="""The conceptual category to which the subject belongs to. This can be a string denoting the category or a term from a controlled vocabulary. This slot is deliberately underspecified. Conceptual categories can range from those that are found in general upper ontologies such as BFO (e.g. process, temporal region, etc) to those that serve as upper ontologies in specific domains, such as COB or BioLink (e.g. gene, disease, chemical entity). The purpose of this optional field is documentation for human reviewers - when a category is known and documented clearly, the cost of interpreting and evaluating the mapping decreases.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': '(The CURIE of the Uberon term for "anatomical '
                                      'entity".)',
                       'value': 'UBERON:0001062'},
                      {'description': '(A string, rather than ID, describing the '
                                      '"anatomical entity" category. This is possible, '
                                      'but less preferred than using an ID.)',
                       'value': 'anatomical entity'},
                      {'description': '(The CURIE of the biolink class for genes.)',
                       'value': 'biolink:Gene'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/13',
                      'https://github.com/mapping-commons/sssom/issues/256']} })
    predicate_id: str = Field(default=..., description="""The ID of the predicate or relation that relates the subject and object of this match.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': 'The subject and the object are instances (owl '
                                      'individuals), and the two instances are the '
                                      'same.',
                       'value': 'owl:sameAs'},
                      {'description': 'The subject and the object are classes (owl '
                                      'class), and the two classes are the same.',
                       'value': 'owl:equivalentClass'},
                      {'description': 'The subject and the object are properties (owl '
                                      'object, data, annotation properties), and the '
                                      'two properties are the same.',
                       'value': 'owl:equivalentProperty'},
                      {'description': 'The subject and the object are classes (owl '
                                      'class), and the subject is a subclass of the '
                                      'object.',
                       'value': 'rdfs:subClassOf'},
                      {'description': 'The subject and the object are properties (owl '
                                      'object, data, annotation properties), and the '
                                      'subject is a subproperty of the object.',
                       'value': 'rdfs:subPropertyOf'},
                      {'description': 'The subject and the object are associated in '
                                      'some unspecified way.',
                       'value': 'skos:relatedMatch'},
                      {'description': 'The subject and the object are sufficiently '
                                      'similar that they can be used interchangeably '
                                      'in some information retrieval applications.',
                       'value': 'skos:closeMatch'},
                      {'description': 'The subject and the object can, with a high '
                                      'degree of confidence, be used interchangeably '
                                      'across a wide range of information retrieval '
                                      'applications.',
                       'value': 'skos:exactMatch'},
                      {'description': 'From the SKOS primer: A triple skos:narrower '
                                      '(and skos:narrowMatch) asserts that , the '
                                      'object of the triple, is a narrower concept '
                                      'than , the subject of the triple.',
                       'value': 'skos:narrowMatch'},
                      {'description': 'From the SKOS primer: A triple skos:broader '
                                      '(and skos:broadMatch) asserts that , the object '
                                      'of the triple, is a broader concept than , the '
                                      'subject of the triple.',
                       'value': 'skos:broadMatch'},
                      {'description': 'Two terms are related in some way. The meaning '
                                      'is frequently consistent across a single set of '
                                      'mappings. Note this property is often '
                                      'overloaded even where the terms are of a '
                                      'different nature (e.g. interpro2go)',
                       'value': 'oboInOwl:hasDbXref'},
                      {'description': 'The subject and the object are associated in '
                                      'some unspecified way. The object IRI often '
                                      'resolves to a resource on the web that provides '
                                      'additional information.',
                       'value': 'rdfs:seeAlso'}],
         'mappings': ['owl:annotatedProperty'],
         'slot_uri': 'owl:annotatedProperty'} })
    predicate_label: Optional[str] = Field(default=None, description="""The label of the predicate/relation of the mapping""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': 'The label of the oboInOwl:hasDbXref property to '
                                      'represent cross-references.',
                       'value': 'has cross-reference'}]} })
    predicate_modifier: Optional[PredicateModifierEnum] = Field(default=None, description="""A modifier for negating the predicate. See https://github.com/mapping-commons/sssom/issues/40 for discussion""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': 'Negates the predicate, see documentation of '
                                      'predicate_modifier_enum',
                       'value': 'Not'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/107']} })
    object_id: str = Field(default=..., description="""The ID of the object of the mapping.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': 'The CURIE denoting the Human Phenotype Ontology '
                                      "concept of 'Thickened ears'",
                       'value': 'HP:0009894'}],
         'mappings': ['owl:annotatedTarget'],
         'slot_uri': 'owl:annotatedTarget'} })
    object_label: Optional[str] = Field(default=None, description="""The label of object of the mapping""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'value': 'Thickened ears'}],
         'recommended': True} })
    object_category: Optional[str] = Field(default=None, description="""The conceptual category to which the subject belongs to. This can be a string denoting the category or a term from a controlled vocabulary. This slot is deliberately underspecified. Conceptual categories can range from those that are found in general upper ontologies such as BFO (e.g. process, temporal region, etc) to those that serve as upper ontologies in specific domains, such as COB or BioLink (e.g. gene, disease, chemical entity). The purpose of this optional field is documentation for human reviewers - when a category is known and documented clearly, the cost of interpreting and evaluating the mapping decreases.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': '(The CURIE of the Uberon term for "anatomical '
                                      'entity".)',
                       'value': 'UBERON:0001062'},
                      {'description': '(A string, rather than ID, describing the '
                                      '"anatomical entity" category. This is possible, '
                                      'but less preferred than using an ID.)',
                       'value': 'anatomical entity'},
                      {'description': '(The CURIE of the biolink class for genes.)',
                       'value': 'biolink:Gene'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/13',
                      'https://github.com/mapping-commons/sssom/issues/256']} })
    mapping_justification: str = Field(default=..., description="""A mapping justification is an action (or the written representation of that action) of showing a mapping to be right or reasonable.""", json_schema_extra = { "linkml_meta": {'any_of': [{'equals_string': 'semapv:LexicalMatching'},
                    {'equals_string': 'semapv:LogicalReasoning'},
                    {'equals_string': 'semapv:CompositeMatching'},
                    {'equals_string': 'semapv:UnspecifiedMatching'},
                    {'equals_string': 'semapv:SemanticSimilarityThresholdMatching'},
                    {'equals_string': 'semapv:LexicalSimilarityThresholdMatching'},
                    {'equals_string': 'semapv:MappingChaining'},
                    {'equals_string': 'semapv:MappingReview'},
                    {'equals_string': 'semapv:ManualMappingCuration'}],
         'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'value': 'semapv:LexicalMatching'},
                      {'value': 'semapv:ManualMappingCuration'}]} })
    author_id: Optional[list[str]] = Field(default=None, description="""Identifies the persons or groups responsible for asserting the mappings. Recommended to be a list of ORCIDs or otherwise identifying URIs.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'], 'slot_uri': 'pav:authoredBy'} })
    author_label: Optional[list[str]] = Field(default=None, description="""A string identifying the author of this mapping. In the spirit of provenance, consider using author_id instead.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    reviewer_id: Optional[list[str]] = Field(default=None, description="""Identifies the persons or groups that reviewed and confirmed the mapping. Recommended to be a list of ORCIDs or otherwise identifying URIs.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    reviewer_label: Optional[list[str]] = Field(default=None, description="""A string identifying the reviewer of this mapping. In the spirit of provenance, consider using reviewer_id instead.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    creator_id: Optional[list[str]] = Field(default=None, description="""Identifies the persons or groups responsible for the creation of the mapping. The creator is the agent that put the mapping in its published form, which may be different from the author, which is a person that was actively involved in the assertion of the mapping. Recommended to be a list of ORCIDs or otherwise identifying URIs.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'dcterms:creator'} })
    creator_label: Optional[list[str]] = Field(default=None, description="""A string identifying the creator of this mapping. In the spirit of provenance, consider using creator_id instead.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping']} })
    license: Optional[str] = Field(default=None, description="""A url to the license of the mapping. In absence of a license we assume no license.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'dcterms:license'} })
    subject_type: Optional[EntityTypeEnum] = Field(default=None, description="""The type of entity that is being mapped.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'owl:Class'}],
         'instantiates': ['sssom:Propagatable']} })
    subject_source: Optional[str] = Field(default=None, description="""URI of vocabulary or identifier source for the subject.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': 'A persistent OBO CURIE pointing to the latest '
                                      'version of the Mondo ontology.',
                       'value': 'obo:mondo.owl'},
                      {'description': 'A Wikidata identifier for the Uberon ontology '
                                      'resource.',
                       'value': 'wikidata:Q7876491'}],
         'instantiates': ['sssom:Propagatable']} })
    subject_source_version: Optional[str] = Field(default=None, description="""Version IRI or version string of the source of the subject term.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': '(A persistent Version IRI pointing to the Mondo '
                                      "version '2021-01-30')",
                       'value': 'http://purl.obolibrary.org/obo/mondo/releases/2021-01-30/mondo.owl'}],
         'instantiates': ['sssom:Propagatable']} })
    object_type: Optional[EntityTypeEnum] = Field(default=None, description="""The type of entity that is being mapped.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'owl:Class'}],
         'instantiates': ['sssom:Propagatable']} })
    object_source: Optional[str] = Field(default=None, description="""URI of vocabulary or identifier source for the object.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': 'A persistent OBO CURIE pointing to the latest '
                                      'version of the Mondo ontology.',
                       'value': 'obo:mondo.owl'},
                      {'description': 'A Wikidata identifier for the Uberon ontology '
                                      'resource.',
                       'value': 'wikidata:Q7876491'}],
         'instantiates': ['sssom:Propagatable']} })
    object_source_version: Optional[str] = Field(default=None, description="""Version IRI or version string of the source of the object term.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'description': '(A persistent Version IRI pointing to the Mondo '
                                      "version '2021-01-30')",
                       'value': 'http://purl.obolibrary.org/obo/mondo/releases/2021-01-30/mondo.owl'}],
         'instantiates': ['sssom:Propagatable']} })
    mapping_provider: Optional[str] = Field(default=None, description="""URL pointing to the source that provided the mapping, for example an ontology that already contains the mappings, or a database from which it was derived.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable']} })
    mapping_source: Optional[str] = Field(default=None, description="""The mapping set this mapping was originally defined in. mapping_source is used for example when merging multiple mapping sets or deriving one mapping set from another.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'value': 'MONDO_MAPPINGS:mondo_exactmatch_ncit.sssom.tsv'}]} })
    mapping_cardinality: Optional[MappingCardinalityEnum] = Field(default=None, description="""A string indicating whether this mapping is from a 1:1 (the subject_id maps to a single object_id), 1:n (the subject maps to more than one object_id), n:1, 1:0, 0:1 or n:n group. Note that this is a convenience field that should be derivable from the mapping set.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    mapping_tool: Optional[str] = Field(default=None, description="""A reference to the tool or algorithm that was used to generate the mapping. Should be a URL pointing to more info about it, but can be free text.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'https://github.com/AgreementMakerLight/AML-Project'}],
         'instantiates': ['sssom:Propagatable']} })
    mapping_tool_version: Optional[str] = Field(default=None, description="""Version string that denotes the version of the mapping tool used.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'v3.2'}],
         'instantiates': ['sssom:Propagatable']} })
    mapping_date: Optional[date] = Field(default=None, description="""The date the mapping was asserted. This is different from the date the mapping was published or compiled in a SSSOM file.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable'],
         'slot_uri': 'pav:authoredOn'} })
    publication_date: Optional[date] = Field(default=None, description="""The date the mapping was published. This is different from the date the mapping was asserted.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'dcterms:created'} })
    confidence: Optional[float] = Field(default=None, description="""A score between 0 and 1 to denote the confidence or probability that the match is correct, where 1 denotes total confidence.""", ge=0.0, le=1.0, json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    curation_rule: Optional[list[str]] = Field(default=None, description="""A curation rule is a (potentially) complex condition executed by an agent that led to the establishment of a mapping. Curation rules often involve complex domain-specific considerations, which are hard to capture in an automated fashion. The curation rule is captured as a resource rather than a string, which enables higher levels of transparency and sharing across mapping sets. The URI representation of the curation rule is expected to be a resolvable identifier which provides details about the nature of the curation rule.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/166',
                      'https://github.com/mapping-commons/sssom/pull/258',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/curation_rule.sssom.tsv']} })
    curation_rule_text: Optional[list[str]] = Field(default=None, description="""A curation rule is a (potentially) complex condition executed by an agent that led to the establishment of a mapping. Curation rules often involve complex domain-specific considerations, which are hard to capture in an automated fashion. The curation rule should be captured as a resource (entity reference) rather than a string (see curation_rule element), which enables higher levels of transparency and sharing across mapping sets. The textual representation of curation rule is intended to be used in cases where (1) the creation of a resource is not practical from the perspective of the mapping_provider and (2) as an additional piece of metadata to augment the curation_rule element with a human readable text.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/166',
                      'https://github.com/mapping-commons/sssom/pull/258',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/curation_rule_text.sssom.tsv']} })
    subject_match_field: Optional[list[str]] = Field(default=None, description="""A list of properties (term annotations on the subject) that was used for the match.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable']} })
    object_match_field: Optional[list[str]] = Field(default=None, description="""A list of properties (term annotations on the object) that was used for the match.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'instantiates': ['sssom:Propagatable']} })
    match_string: Optional[list[str]] = Field(default=None, description="""String that is shared by subj/obj. It is recommended to indicate the fields for the match using the object and subject_match_field slots.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping']} })
    subject_preprocessing: Optional[list[str]] = Field(default=None, description="""Method of preprocessing applied to the fields of the subject. If different preprocessing steps were performed on different fields, it is recommended to store the match in separate rows.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'semapv:Stemming'},
                      {'value': 'semapv:StopWordRemoval'}],
         'instantiates': ['sssom:Propagatable']} })
    object_preprocessing: Optional[list[str]] = Field(default=None, description="""Method of preprocessing applied to the fields of the object. If different preprocessing steps were performed on different fields, it is recommended to store the match in separate rows.""", json_schema_extra = { "linkml_meta": {'annotations': {'propagated': {'tag': 'propagated', 'value': True}},
         'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'examples': [{'value': 'semapv:Stemming'},
                      {'value': 'semapv:StopWordRemoval'}],
         'instantiates': ['sssom:Propagatable']} })
    similarity_score: Optional[float] = Field(default=None, description="""A score between 0 and 1 to denote the similarity between two entities, where 1 denotes equivalence, and 0 denotes disjointness. The score is meant to be used in conjunction with the similarity_measure field, to document, for example, the lexical or semantic match of a matching algorithm.""", ge=0.0, le=1.0, json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/385',
                      'https://github.com/mapping-commons/sssom/pull/386',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/similarity_score.sssom.tsv']} })
    similarity_measure: Optional[str] = Field(default=None, description="""The measure used for computing a similarity score. This field is meant to be used in conjunction with the similarity_score field, to document, for example, the lexical or semantic match of a matching algorithm. To make processing this field as unambiguous as possible, we recommend using wikidata CURIEs, but the type of this field is deliberately unspecified.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': '(the Wikidata IRI for the Jaccard index '
                                      'measure).',
                       'value': 'https://www.wikidata.org/entity/Q865360'},
                      {'description': '(the Wikidata CURIE for the Jaccard index '
                                      'measure).',
                       'value': 'wikidata:Q865360'},
                      {'description': '(a score to measure the distance between two '
                                      'character sequences).',
                       'value': 'Levenshtein distance'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/385',
                      'https://github.com/mapping-commons/sssom/pull/386',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/similarity_score.sssom.tsv']} })
    see_also: Optional[list[str]] = Field(default=None, description="""A URL specific for the mapping instance. E.g. for kboom we have a per-mapping image that shows surrounding axioms that drive probability. Could also be a github issue URL that discussed a complicated alignment""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'rdfs:seeAlso'} })
    issue_tracker_item: Optional[str] = Field(default=None, description="""The issue tracker item discussing this mapping.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping', 'TermMapping'],
         'examples': [{'description': '(A URL resolving to an issue discussing a new '
                                      'SSSOM element request)',
                       'value': 'SSSOM_GITHUB_ISSUE:166'}],
         'see_also': ['https://github.com/mapping-commons/sssom/issues/78',
                      'https://github.com/mapping-commons/sssom/pull/259',
                      'https://github.com/mapping-commons/sssom/blob/master/examples/schema/issue_tracker_item.sssom.tsv']} })
    other: Optional[str] = Field(default=None, description="""Pipe separated list of key value pairs for properties not part of the SSSOM spec. Can be used to encode additional provenance data.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping']} })
    comment: Optional[str] = Field(default=None, description="""Free text field containing either curator notes or text generated by tool providing additional informative information.""", json_schema_extra = { "linkml_meta": {'domain_of': ['mapping set', 'mapping', 'TermMapping'],
         'slot_uri': 'rdfs:comment'} })

    @field_validator('predicate_id')
    def pattern_predicate_id(cls, v):
        pattern=re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:\S+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid predicate_id format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid predicate_id format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('object_id')
    def pattern_object_id(cls, v):
        pattern=re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:\S+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid object_id format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid object_id format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('mapping_justification')
    def pattern_mapping_justification(cls, v):
        pattern=re.compile(r"^semapv:(MappingReview|ManualMappingCuration|LogicalReasoning|LexicalMatching|CompositeMatching|UnspecifiedMatching|SemanticSimilarityThresholdMatching|LexicalSimilarityThresholdMatching|MappingChaining)$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid mapping_justification format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid mapping_justification format: {v}"
            raise ValueError(err_msg)
        return v


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
MappingSet.model_rebuild()
Mapping.model_rebuild()
MappingRegistry.model_rebuild()
MappingSetReference.model_rebuild()
Prefix.model_rebuild()
ExtensionDefinition.model_rebuild()
Propagatable.model_rebuild()
NoTermFound.model_rebuild()
SourceRelease.model_rebuild()
ReleaseMetadata.model_rebuild()
Term.model_rebuild()
Synonym.model_rebuild()
Relationship.model_rebuild()
TermMapping.model_rebuild()
