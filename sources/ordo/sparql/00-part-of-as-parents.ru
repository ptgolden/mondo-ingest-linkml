# Copied verbatim from monarch-initiative/mondo-ingest@0dc67c4 src/sparql/ordo-construct-subclass-from-part-of.ru
# Runs before every SELECT here: Mondo reads ORDO's part_of as hierarchy, so parents,
# scope and subsets are all computed over subClassOf with part_of folded in, as in
# mondo-ingest's recipe.
prefix owl: <http://www.w3.org/2002/07/owl#>
prefix BFO: <http://purl.obolibrary.org/obo/BFO_>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>

DELETE {
  ?x rdfs:subClassOf ?super .
   ?super a owl:Restriction ;
   owl:onProperty BFO:0000050 ;
   owl:someValuesFrom ?y
}
INSERT {
  ?x rdfs:subClassOf ?y
}
WHERE {
  ?x rdfs:subClassOf ?super .
   ?super a owl:Restriction ;
   owl:onProperty BFO:0000050 ;
   owl:someValuesFrom ?y
}
