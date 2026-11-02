# mondo-ingest/: files copied from mondo-ingest

Inputs every source's bundle needs so that it matches what mondo-ingest builds and
consumes, copied from monarch-initiative/mondo-ingest@0dc67c4:

| File | From | Used for |
|---|---|---|
| `classes.sparql` | `src/sparql/classes.sparql` | the mirror and component signature reports |
| `prefixes.csv` | `src/ontology/config/prefixes.csv` | `semsql make <source>.db` (mondo-ingest's `%.db` rule) |

A source's own copied files (ORDO's `ordo.metadata.sssom.yml`) are in its directory.

Mondo's interpretation of a source is not here. It's in the extraction queries (the
shared `sparql/` and the source's own), which produce `<source>.yaml` directly.
