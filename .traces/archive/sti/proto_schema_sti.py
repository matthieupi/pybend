"""Polymorphic schema extension — STI (Single Table Inheritance) support.

Registers a 'polymorphic' stage in the schema pipeline (after 'defs')
that generates oneOf + discriminator mapping for STI root models,
and marks the discriminator field on subtypes with ui.display=false.

Activated by importing from proto_model.py at module load time.
"""

import logging

from n3tx.core import config
from n3tx.core.models.proto_schema import schema_extension
from n3tx.core.models.proto_dump import dump_extension

logger = logging.getLogger('n3tx.schema')


@schema_extension(after='defs')
def polymorphic(cls, s: dict) -> dict:
    """Generate oneOf + discriminator for STI root, const discriminator for subtypes."""
    disc = getattr(cls, '__discriminator__', None)
    root = getattr(cls, '__sti_root__', None)
    if not disc or not root:
        return s

    if cls is root:
        # STI root: build oneOf + discriminator mapping from subtypes
        subtypes = getattr(root, '__subtypes__', {})
        if not subtypes:
            return s

        if '$defs' not in s:
            s['$defs'] = {}

        mapping = {}
        one_of = []

        # Include root itself if not abstract
        if not getattr(cls, '__abstract__', False):
            mapping[cls.__name__] = f"#/$defs/{cls.__name__}"
            root_schema = _subtype_schema(cls, disc)
            s['$defs'][cls.__name__] = root_schema
            one_of.append({'$ref': f"#/$defs/{cls.__name__}"})

        # Add each subtype
        for name, subtype in subtypes.items():
            if getattr(subtype, '__abstract__', False):
                continue
            mapping[name] = f"#/$defs/{name}"
            sub_schema = _subtype_schema(subtype, disc)
            s['$defs'][name] = sub_schema
            one_of.append({'$ref': f"#/$defs/{name}"})

        if one_of:
            s['oneOf'] = one_of
            s['discriminator'] = {
                'propertyName': disc,
                'mapping': mapping,
            }
    else:
        # STI subtype: mark discriminator as const with ui.display=false
        if 'properties' in s and disc in s['properties']:
            s['properties'][disc]['const'] = cls.__name__
            s['properties'][disc].setdefault('ui', {})['display'] = False

    return s


def _subtype_schema(cls, disc_name: str) -> dict:
    """Build a schema entry for a subtype (or root) in $defs."""
    from n3tx.core.models.proto_model import _apply_field_exclusion
    from n3tx.core.authorize.schema import access_schema

    schema = cls.referenced_json_schema()
    schema.pop('$defs', None)

    # Add metadata
    schema['$id'] = f"{config.API_URL}/{cls.__name__}"
    schema['__name__'] = cls.__name__
    schema['__tablename__'] = getattr(cls, '__tablename__', '')

    # Methods
    schema['methods'] = cls.__n3tx_methods_json_signature__()

    # Access rules
    schema['access'] = access_schema(cls)

    # UI: field exclusion
    _apply_field_exclusion(schema)

    # UI config
    ui_config = getattr(cls, '__ui__', None)
    if ui_config:
        schema['ui'] = dict(ui_config)

    # Discriminator property: const + hidden
    if 'properties' in schema and disc_name in schema['properties']:
        schema['properties'][disc_name]['const'] = cls.__name__
        schema['properties'][disc_name].setdefault('ui', {})['display'] = False

    return schema


@dump_extension(after='instance_url')
def sti_type(instance, d: dict) -> dict:
    """Ensure discriminator ui.display=false hint in schema for STI responses.

    The discriminator value is already in the response (it's a real Pydantic field),
    so this stage is a no-op for the data. It exists as a hook point for any
    future STI-specific dump logic.
    """
    return d
