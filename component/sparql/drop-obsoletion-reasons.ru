# Drop the release's free-text obsoletion reasons (rendered as rdfs:comment on the
# class). mondo-ingest's ORDO component never carried them: ORDO's
# efo:reason_for_inactivation is not in its property map, so it was filtered out.
prefix owl: <http://www.w3.org/2002/07/owl#>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>

DELETE { ?c rdfs:comment ?reason }
WHERE  { ?c a owl:Class ; rdfs:comment ?reason }
