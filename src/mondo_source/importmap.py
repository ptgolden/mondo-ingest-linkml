"""The LinkML importmap for the schema.

The schema imports SSSOM's by a URL. The importmap points that import at the
installed sssom-schema package, so nothing is fetched. Run as a module, it prints
the importmap as JSON, for the tools that take it as a file.
"""

import json
from importlib import resources


def importmap() -> dict[str, str]:
    """The schema's `sssom_schema:` prefix, mapped to the installed package's schema directory."""
    return {"sssom_schema:": f"{resources.files('sssom_schema') / 'schema'}/"}


if __name__ == "__main__":
    print(json.dumps(importmap()))
