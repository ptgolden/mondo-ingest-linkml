# Adapted from monarch-initiative/mondo-ingest@0dc67c4 src/sparql/ordo-construct-d2g.ru
# Changes:
# - Gene HGNC ids come from the rendering's IRI-valued oboInOwl:hasDbXref
#   (http://identifiers.org/hgnc/N), not from "HGNC:N" string literals.
# - No rdfs:label from ORDO's gene symbol: mondo-ingest's component drops the
#   HGNC classes' labels anyway (they are outside the relevant signature).
# - Orphanet:410295 "disease-causing germline mutation(s) (loss of function) in"
#   maps to RO:0004002 "has material basis in loss of function germline mutation
#   in". mondo-ingest maps it to RO:0004001, the gain-of-function relation.
prefix oio: <http://www.geneontology.org/formats/oboInOwl#>
prefix owl: <http://www.w3.org/2002/07/owl#>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix Orphanet: <http://www.orpha.net/ORDO/Orphanet_>
prefix RO: <http://purl.obolibrary.org/obo/RO_>

INSERT {
  ?hgncGene a owl:Class .
  ?disease
     rdfs:subClassOf
      [
          a owl:Restriction ;
          owl:onProperty ?oboRel ;
          owl:someValuesFrom ?hgncGene
      ]
}
WHERE {
  ?gene rdfs:subClassOf [
               owl:onProperty ?ordoRel ;
               owl:someValuesFrom ?disease ] ;
        oio:hasDbXref ?hgncGene ;
        rdfs:subClassOf+ Orphanet:C010 .
  ?disease rdfs:label ?diseaseLabel ;
           rdfs:subClassOf+ Orphanet:C001 .
  FILTER( STRSTARTS(STR(?hgncGene), "http://identifiers.org/hgnc/") )
  VALUES (?ordoRel ?oboRel) {
    ( Orphanet:410295 RO:0004002 )
    ( Orphanet:410296 RO:0004001 )
    ( Orphanet:317343 RO:0004003 )
    ( Orphanet:317344 RO:0004004 )
  }
}
