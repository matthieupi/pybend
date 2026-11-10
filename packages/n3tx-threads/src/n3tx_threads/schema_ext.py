"""Descriptive TTX metadata via the native default pipeline's ttx stage.

API: ttx(cls, schema) enriches canonical TTX, typed views and matching host
definitions after metadata. Native stages own fields, methods, access, IDs and
definitions. Typed views describe their kind and empty backing data; canonical
data has no kind-specific schema validation. Runtime value decoding is separate.

Importing n3tx_threads registers this stage in the default pipeline only. The
ttx metadata describes projection; it does not redirect routes or browser NTT
entities. Native complex/recursive schema and reference-closure limitations are
not repaired by this stage."""

from n3tx_core import config
from n3tx_core.models.proto_schema import schema_extension

from .ttx import TTX, _KNOWN_KINDS


def _decorate(cls: type[TTX], schema: dict) -> None:
    """Attach projection metadata and the concrete representation invariant."""
    # 0. Preserve named type identity; canonical entity identity is descriptive.
    schema["ttx"] = {
        "canonical_model": "TTX",
        "canonical_schema": f"{config.API_URL}/TTX",
        "kind_field": "kind",
        "transport_kind": "meta.kind",
        "representation": "canonical" if cls is TTX else "typed",
    }
    if cls is not TTX:
        # 1. Typed views carry content in native declared fields, not data.
        properties = schema.setdefault("properties", {})
        properties.setdefault("kind", {}).update(
            const=cls.__name__, default=cls.__name__,
        )
        properties.setdefault("data", {}).update(maxProperties=0)


@schema_extension(after="metadata")
def ttx(cls, schema: dict) -> dict:
    """Enrich TTX representations and only matching native host definitions."""
    # 0. Ordinary native discovery already owns method return references.
    if issubclass(cls, TTX):
        _decorate(cls, schema)
    # 1. Enrich existing named resources without creating or repairing defs.
    definitions = schema.get("$defs", {})
    for typed in (TTX, *_KNOWN_KINDS.values()):
        definition = definitions.get(typed.__name__)
        if not isinstance(definition, dict):
            continue
        if definition.get("$id") != f"{config.API_URL}/{typed.__name__}":
            continue
        _decorate(typed, definition)
    return schema


# Changelog (Python has no block-comment syntax).
# - 2026-11-09: Register native ttx projection metadata and conditional known
#   payload schemas, with namespaced nested definitions and typed kind/data
#   invariants; preserve method discovery, named schema IDs and raw fallback.
#   Resolve recursive model roots before payload extraction; keep embedded
#   resource reference closure and scope private native definition copies to
#   their containing TTX resource without changing public schema identities.
# - 2026-11-09: Keep descriptive native metadata and typed kind/data invariants;
#   remove payload composition, conditional data validation and ref repair.
#   Leave complex/recursive schemas and reference closure to native stages.
