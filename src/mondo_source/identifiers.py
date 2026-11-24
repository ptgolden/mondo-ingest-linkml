"""The identifiers in a term as a source states it, made canonical.

A source has its identifiers as IRIs, or as CURIEs in its own spelling of the prefix.
The prefix map (prefixes.yaml, a curies extended prefix map) gives each its canonical
CURIE: ORDO's "ICD-10:" and "MeSH:" become "ICD10:" and "MESH:". An identifier with no
prefix in the map fails.

The schema says which slots hold identifiers.
"""

from collections.abc import Iterator
from dataclasses import dataclass

import curies
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import JsonValue

type SlotPath = tuple[str, ...]
"""A slot of a class, or of an object nested in one: ("parents",), ("mappings", "object_id")."""


def identifier_slots(schema: SchemaView, class_name: str, path: SlotPath = ()) -> Iterator[SlotPath]:
    """The slots of a class, and of the objects nested in it, that hold identifiers:
    references to other objects, and values whose type is a kind of uriorcurie."""
    for slot in schema.class_induced_slots(class_name):
        assert slot.range is not None  # an induced slot has its own or the schema's default
        here = (*path, slot.name)
        if schema.is_inlined(slot):
            yield from identifier_slots(schema, slot.range, here)
        elif slot.range in schema.all_classes():
            yield here
        elif slot.range in schema.all_types() and "uriorcurie" in schema.type_ancestors(slot.range):
            yield here


@dataclass(frozen=True)
class Identifiers:
    """The slots that hold identifiers, and the prefix map their CURIEs come from."""

    slots: frozenset[SlotPath]
    converter: curies.Converter

    def to_curies(self, stated: JsonValue, path: SlotPath = ()) -> JsonValue:
        """A stated term, or the part of one at path, with each identifier as its
        canonical CURIE."""
        match stated:
            case dict():
                return {slot: self.to_curies(value, (*path, slot)) for slot, value in stated.items()}
            case list():
                return [self.to_curies(value, path) for value in stated]
            case str() if path in self.slots:
                return self.curie(stated, path)
            case _:
                return stated

    def curie(self, identifier: str, slot: SlotPath) -> str:
        """The canonical CURIE for an IRI, or for a CURIE in any spelling of its prefix."""
        curie = self.converter.compress_or_standardize(identifier)
        if curie is None:
            raise ValueError(f"{'.'.join(slot)}: no prefix in the prefix map for {identifier!r}")
        return curie
