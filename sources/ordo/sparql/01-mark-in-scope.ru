# Mark the classes Mondo takes in from ORDO. Every SELECT here keeps only these.
#
# In scope: the descendants of Disorder, Group of disorders, Subtype of a disorder
# and Inactive clinical entity, except gene classes (as in mondo-ingest's
# ordo-relevant-signature.sparql), plus the named ancestors of those roots
# (Orphanet:C001), which mondo-ingest's component keeps as referenced classes.
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix oio: <http://www.geneontology.org/formats/oboInOwl#>

INSERT { ?term <https://w3id.org/monarch-initiative/mondo-source/in_scope> true }
WHERE {
  VALUES ?root {
    <http://www.orpha.net/ORDO/Orphanet_557493>
    <http://www.orpha.net/ORDO/Orphanet_557492>
    <http://www.orpha.net/ORDO/Orphanet_557494>
    <http://www.orpha.net/ORDO/Orphanet_C041>
  }
  { ?term rdfs:subClassOf* ?root .
    FILTER NOT EXISTS { ?term oio:hasDbXref ?x FILTER(STRSTARTS(STR(?x), "HGNC:")) } }
  UNION
  { ?root rdfs:subClassOf+ ?term }
  FILTER(isIRI(?term) && STRSTARTS(STR(?term), "http://www.orpha.net/ORDO/Orphanet_"))
}
