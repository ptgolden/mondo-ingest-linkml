# Rewrite what Mondo reads from ORDO into OBO-in-OWL conventions, so mondo-source's
# shared queries (terms, synonyms, consider) read it. ORDO itself uses none of the
# OBO properties written here.
#
# - efo:alternative_term: unscoped in ORDO; Mondo reads them as EXACT (mondo-ingest's
#   property map).
# - efo:definition -> IAO:0000115. ORDO's only citation for any definition is
#   "Orphanet"; not taken in.
# - Everything under Inactive clinical entity (C041), including C041 and its own
#   category classes, is deprecated (mondo-ingest's fix_deprecated.ru). ORDO's
#   free-text reason_for_inactivation is not taken in.
# - "Moved to" (C056), which ORDO defines as redirection to a code of replacement
#   -> IAO:0100001 (term replaced by).
# - "Referred to" (C057), which suggests a target without claiming replacement
#   -> oboInOwl:consider.
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX efo: <http://www.ebi.ac.uk/efo/>
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX oio: <http://www.geneontology.org/formats/oboInOwl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

INSERT { ?id oio:hasExactSynonym ?s } WHERE { ?id efo:alternative_term ?s } ;

INSERT { ?id obo:IAO_0000115 ?d } WHERE { ?id efo:definition ?d } ;

INSERT { ?id owl:deprecated "true"^^xsd:boolean }
WHERE { ?id rdfs:subClassOf* <http://www.orpha.net/ORDO/Orphanet_C041> } ;

INSERT { ?id obo:IAO_0100001 ?target }
WHERE { ?id rdfs:subClassOf [ owl:onProperty <http://www.orpha.net/ORDO/Orphanet_C056> ; owl:someValuesFrom ?target ] } ;

INSERT { ?id oio:consider ?target }
WHERE { ?id rdfs:subClassOf [ owl:onProperty <http://www.orpha.net/ORDO/Orphanet_C057> ; owl:someValuesFrom ?target ] }
