# mondo-ingest/: files copied from mondo-ingest

Inputs the ORDO bundle needs so that it matches what mondo-ingest builds and consumes,
copied from monarch-initiative/mondo-ingest@0dc67c4:

| File | From | Used for |
|---|---|---|
| `classes.sparql` | `src/sparql/classes.sparql` | the mirror and component signature reports |
| `prefixes.csv` | `src/ontology/config/prefixes.csv` | `semsql make ordo.db` (mondo-ingest's `%.db` rule) |
| `ordo.metadata.sssom.yml` | `src/ontology/metadata/ordo.metadata.sssom.yml` | the header of `ordo.sssom.tsv` |

Mondo's interpretation of ORDO itself is not here. It's in the extraction queries
(`sparql/`), which produce `ordo.yaml` directly. Earlier, at tag `original-yaml-approach`,
it was a separate step that ran mondo-ingest's ORDO recipe on an OWL rendering of a
faithful YAML.
