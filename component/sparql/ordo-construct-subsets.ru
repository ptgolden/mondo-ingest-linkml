# Adapted from monarch-initiative/mondo-ingest@0dc67c4 src/sparql/ordo-construct-subsets.ru
# Change: LCASE the category label. ORDO 4.7's category labels were lowercase
# ("disorder"); 4.9's are capitalised ("Disorder"), so the unchanged query would
# rename Mondo's existing subsets (mondo#ordo_disorder -> mondo#ordo_Disorder).
prefix oio: <http://www.geneontology.org/formats/oboInOwl#>
prefix phenome: <http://www.orpha.net/ORDO/Orphanet_C001>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>

INSERT {
  ?cls oio:inSubset ?subset
}
WHERE {
  ?category rdfs:subClassOf phenome: .
  ?cls rdfs:subClassOf+ ?category .
  ?category rdfs:label ?categoryLabel .
  BIND( URI(CONCAT("http://purl.obolibrary.org/obo/mondo#ordo_", REPLACE(LCASE(STR(?categoryLabel)), " ", "_"))) AS ?subset)
}
