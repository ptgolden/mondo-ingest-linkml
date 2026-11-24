# Shared extraction queries

The default query for each Term slot whose OBO-in-OWL reading is standard. A source
replaces one by putting a file of the same name in its own `sparql/`, and adds its own
for slots not here (mappings, relationships, subsets).

They assume two things of the source's updates (`*.ru`, which run first):

- every class Mondo takes in is marked
  `<https://w3id.org/monarch-initiative/mondo-source/in_scope> true`;
- anything Mondo reads differently from OBO conventions has been rewritten into them
  (e.g. ORDO's `efo:alternative_term` as `oboInOwl:hasExactSynonym`).

| Query | Slot | Reads |
|---|---|---|
| `terms.rq` | label, deprecated, definition, replaced_by | `rdfs:label`, `owl:deprecated true`, IAO:0000115, IAO:0100001 |
| `synonyms.rq` | synonyms | `oboInOwl:has{Exact,Related,Broad,Narrow}Synonym` and their `hasSynonymType`, plus the two synonyms Mondo generates from labels |
| `parents.rq` | parents | named `rdfs:subClassOf` parents that are in scope |
| `consider.rq` | consider | `oboInOwl:consider` |
| `metadata.rq` | release metadata | the `owl:Ontology` header |
