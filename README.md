# mondo-source (experiment)

An experiment for [mondo-ingest#925](https://github.com/monarch-initiative/mondo-ingest/issues/925)
("make the alignment system LinkML-first"), with two sources: Orphanet's ORDO and
ICD-10 (WHO).

The question: what does a source repo look like if its one reviewable artifact is a LinkML
YAML of **what Mondo takes in from the source**, with everything mondo-ingest needs rendered
from that YAML, so mondo-ingest only downloads files (as mondo-ingest#906 does for
ICD10WHO)? Can it keep well-defined semantics (OWL in, transformations in SPARQL) with as
little bespoke Python as possible? And how much of it is shared between sources?

An earlier design, which published a faithful YAML of the *whole* source and applied Mondo's
policy afterwards in OWL, is preserved at tag `original-yaml-approach`; its message explains
why it was replaced.

This is not production code.

## Layout

A uv workspace, laid out as the eventual repos would be:

| Directory | What it is | Would become |
|---|---|---|
| `packages/mondo-source` | The shared package: the schema, the prefix map, the shared SPARQL, the Python (one `mondo-source` CLI), the make rules (`source.mk`), and files copied from mondo-ingest | A released package, or part of mondo-ingest |
| `sources/ordo` | ORDO's own: its Makefile settings, SPARQL and SSSOM metadata. [README](sources/ordo/README.md) | ORDO's source repo |
| `sources/icd10who` | ICD10WHO's own, likewise. [README](sources/icd10who/README.md) | Part of mondo-ingest-icd10who |

A source directory holds no Python. ORDO's is 7 SPARQL files; ICD10WHO's is 2.

## Running it

`make` needs only `uv`, `curl` and GNU Make 4.3+: no ROBOT, no Java. `make bundle` also
needs Docker, for the `obolibrary/odkfull:v1.6` image (semsql, and ROBOT's metrics).

In a source directory (`sources/ordo`, `sources/icd10who`):

```sh
make            # download the source if needed; build <source>.yaml and its renderings
make bundle     # also the mirror, its signature, and the semsql db and metrics (Docker)
make validate   # linkml-validate <source>.yaml; sssom validate <source>.sssom.tsv
make refresh    # re-download the source, then build
```

Outputs, in the source's `release/`:

| File | What it is | Role |
|---|---|---|
| `<source>.yaml` | The source's in-scope terms as Mondo reads them, each carrying its SSSOM `mappings`, per the schema | **The target**: reviewed by diffing releases |
| `<source>.metadata.yaml` | The `metadata` block: source version, schema version, generated_at, … | **Target**: the freshness contract |
| `<source>.sssom.tsv` | The terms' mappings, flattened, with mondo-ingest's header | Rendering of `<source>.yaml` |
| `<source>.owl` | `<source>.yaml` as OWL, rendered by linkml-owl | Rendering, transitional until mondo-ingest reads YAML |
| `component_signature-<source>.tsv` | As mondo-ingest builds it, rows sorted by code point | Rendering |
| `mirror-<source>.owl`, `mirror_signature-<source>.tsv` | From `make bundle`; the mirror is the source as downloaded, as RDF/XML | For mondo-ingest's existing checks |
| `<source>.db`, `<source>-metrics.json` | From `make bundle`, as mondo-ingest builds them | For mondo-ingest's existing checks |

The file names are the ones mondo-ingest's targets expect (cf. `ICD10WHO_DOWNLOADS`).

## How it works

```
source RDF --mondo-source assemble: load into Oxigraph, SPARQL updates, SELECTs--> <source>.yaml
<source>.yaml --mondo-source sssom--> <source>.sssom.tsv
<source>.yaml --mondo-source render-owl (linkml-owl, plus header and declarations)--> <source>.owl
```

- **No ROBOT outside the ODK image.** Every source is loaded into an on-disk Oxigraph
  store (`rdfstore.py`), so memory stays bounded however big the source is: all of
  NCIT (812 MB, 10.8M triples) loads with a 2.2 GB peak and queries in about 0.5 GB.
  For a small source this costs time (ORDO's extraction: about 19 s instead of 5 s).
  - The signature reports are `mondo-source select` over the same kind of store.
  - `render-owl` writes the ontology header and annotation property declarations
    itself, on linkml-owl's py-horned-owl document. The result is the same graph
    `robot annotate` made, apart from the build date.
  - The mirror is the download, converted to RDF/XML if it isn't already. mondo-ingest
    made it with `robot merge` + `odk:normalize --add-source true`, which loads the whole
    source into the OWL API to add one ontology annotation that nothing in mondo-ingest
    reads; its readers use `owl:versionIRI`/`owl:versionInfo`, which the download has.
  - Only `robot measure` remains, inside the ODK image for `make bundle`: its
    expressivity and OWL 2 profile metrics need the OWL API.

- **Mondo's reading of a source happens in SPARQL**, run in-process by Oxigraph, from two
  directories: mondo-source's `sparql/` and the source's own `sparql/`. A source file
  replaces a shared one of the same name.
  - Updates (`*.ru`) run first, in name order. A source's updates do two things:
    - mark the classes Mondo takes in, with mondo-source's `in_scope` property;
    - rewrite anything Mondo reads differently from OBO conventions into them (ORDO's
      `part_of` as parents, its `alternative_term` as exact synonyms, …).
  - Each SELECT (`*.rq`) then fills one part of the release, by its name:
    - `terms.rq` returns one row per term with all its single-valued slots;
    - every other `<slot>.rq` fills a multivalued slot (`synonyms.rq` → `Term.synonyms`);
    - a row with columns beyond `?id ?<slot>` is a nested object.
  - The shared queries read OBO-in-OWL: `terms`, `synonyms`, `parents`, `consider` and
    `metadata` ([sparql/README.md](packages/mondo-source/src/mondo_source/sparql/README.md)).
    Sources add their own for what has no OBO convention (ORDO's mappings,
    relationships, subsets), or replace a shared one (ICD10WHO's metadata).
  - Mondo's own additions are shared: `synonyms.rq` generates the label synonyms
    (`mondo:GENERATED_FROM_LABEL`) and the bracket-stripped ones (`mondo:GENERATED`) for
    every source, so the YAML shows what Mondo added rather than the source said.
  - Each query ends in an `ORDER BY`, which is what makes the output deterministic.
  - Queries do no prefix handling. They return IRIs as IRIs, and identifiers a source only
    has as strings (ORDO's xrefs) as literals typed `xsd:anyURI`.
- **The Python leans on libraries**, and none of it is source-specific.
  - `assemble.py` (about 80 lines) groups query rows by term and hands them over:
    - identifiers to `curies`, with `prefixes.yaml` as an extended prefix map. IRIs are
      compressed, and `anyURI` literals are standardised, so ORDO's spellings (`ICD-10`,
      `MeSH`, `ICD-11`) become mondo-ingest's prefixes via `prefix_synonyms`;
    - everything else to the Pydantic models generated from the schema (`gen-pydantic`,
      into the package at build time, not committed). Building them coerces types and
      checks required slots, CURIE patterns and unknown fields.

    Its one check of its own: a term with two values for a single-valued slot fails,
    because keeping either would silently drop the other.
  - `sssom.py` flattens the mappings.
  - `render_owl.py` renders the YAML as OWL with linkml-owl, which reads `owl` annotations
    in the schema: an axiom type per slot, and OWL functional-syntax templates for
    synonyms, relationships, mappings and subsets. Its only additions to linkml-owl are
    adding the release's prefixes and an `iri()` template function (for ICD-10 codes like
    `A98.5+`, which OWL functional syntax can't abbreviate).
  - `yamlio.py` writes YAML that reads back the same under YAML 1.1 and 1.2.

  The CLIs use Typer, and `uv run pyright` is clean.
- **Fail hard.** Assembly stops on:
  - a term with conflicting single-valued slots;
  - an identifier with no prefix in the map;
  - anything the models reject.

## Adding a source

A directory under `sources/` with:
- a `pyproject.toml` depending on `mondo-source`, and a `Makefile` setting `SOURCE`,
  `SOURCE_URL`, `SOURCE_FILE` (RDF/XML as `.owl`, or Turtle) and `SSSOM_METADATA`, then
  including `source.mk`;
- `sparql/` with at least a scope update, plus whatever rewrites the source into OBO
  conventions and whatever queries it needs beyond the shared ones;
- its SSSOM metadata;
- its prefixes, added to the shared `prefixes.yaml`.

## Findings about the approach

- **A second source cost two SPARQL files.** ICD10WHO needed a scope update and a
  metadata query; everything else it uses is shared, and its output matches both
  mondo-ingest's last component and mondo-ingest-icd10who's YAML (see its README).
  Moving ORDO onto the shared queries changed none of its 11,668 terms.
- **Timings (ORDO 4.9, linkml-owl 0.5.0, source already downloaded):**
  - building `ordo.yaml` takes about 35 s (on-disk Oxigraph load, updates, queries,
    models, YAML);
  - `make all bundle` takes about 7 minutes (419 s, 1.3 GB peak), about 5 of them
    linkml-owl rendering `ordo.owl`. Three fixes to linkml-owl (memoising slot lookups,
    compiling each template once, lazy logging arguments) bring that render from 290 s
    to 63 s with identical output; the ROBOT-template rendering it replaced took about
    30 s;
  - for ICD10WHO, `make all` takes 148 s (the render is 114 s of it) and `make bundle`
    35 s more;
  - `make validate` takes about 1.5 minutes for ORDO, almost all YAML parsing.
- **YAML is a cost and a correctness hazard, and stays because curators read it.**
  - The faithful 25 MB YAML of the original approach took 10.8 s to parse with PyYAML's C
    loader, 58.8 s with ruamel (YAML 1.2), and 0.23 s as JSON.
  - The gene alias `2E4` is a string under YAML 1.1 (PyYAML) but the float `20000.0` under
    YAML 1.2. The assembler quotes such strings.
- **CURIE syntax needs an explicit pattern.** `uriorcurie` alone is unconstrained in JSON
  Schema and Pydantic, so the schema puts a pattern on each CURIE slot (one YAML anchor).
  It has to be on the slots: gen-pydantic ignores patterns declared on a type.
- **Mappings are SSSOM, inline on their term.**
  - `Term.mappings` is a `TermMapping`: every slot of the `sssom-schema` package's `mapping`
    class except `subject_id` and `subject_label`.
  - It doesn't subclass `mapping`, because that class requires `subject_id` through a rule
    a subclass would inherit.
  - The SSSOM schema has no PURL for its YAML, so the import is pinned to the v1.0.0 GitHub
    URL, and redirected to the installed package with a LinkML importmap.
    `linkml-validate` has no importmap option and fetches the URL.
- **Timestamps.** ORDO publishes `dcterms:modified` without a timezone, so `source_date` is
  kept as a verbatim string.

## Open questions

- **Steps that need all sources at once.** Nico's concern on #906 still stands: some
  mondo-ingest steps need every source together, and those can't move into a single
  source repo.
- **An audit report.** A report of what each Mondo-interpretation step did (e.g. counts of
  generated synonyms, promoted `part_of` edges) could replace a second, faithful YAML.
- **The non-RDF path.** It isn't exercised here, and may not need to be: every source
  mondo-ingest has (DOID, ICD10CM, ICD10WHO, ICD11, NCIT, OMIM, ORDO) reaches it as RDF,
  the non-RDF ones converted in their own repos. A non-RDF adapter would only have to
  produce what the queries do: rows keyed by term ID, per slot.
- **`mapping_set_id` and PURLs** are placeholders until the PURL scheme is decided.
