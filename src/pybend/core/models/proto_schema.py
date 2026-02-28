"""Proto schema pipeline — composable stages for ProtoModel schema generation.

Each function is a pure dict → dict transformation:

    s = proto_schema.base(cls)
    s = proto_schema.strip_hidden(cls, s)
    s = proto_schema.methods(cls, s)
    s = proto_schema.defs(cls, s)
    s = proto_schema.access(cls, s)
    s = proto_schema.ui(cls, s)
    s = proto_schema.metadata(cls, s)

access() and ui() will move to mixins (AccessMixin, ViewableMixin)
when those are introduced — each mixin's schema() will call super().schema()
then apply its own stage.
"""

from pybend.core import config
from pybend.core.utils.introspection import collect_all_referenced_models, _is_self_ref


def base(cls) -> dict:
    """Pydantic core JSON Schema + Ref['self'] patches."""
    schema = cls.model_json_schema(ref_template="#/$defs/{model}")
    if 'properties' in schema:
        for field_name, field_info in cls.model_fields.items():
            if _is_self_ref(field_info.annotation):
                schema['properties'][field_name] = {"type": "selfref"}
    return schema


def strip_hidden(cls, s: dict) -> dict:
    """Remove __hidden_fields__ from properties and required."""
    hidden = getattr(cls, '__hidden_fields__', set())
    if hidden and 'properties' in s:
        for name in hidden:
            s['properties'].pop(name, None)
        if 'required' in s:
            s['required'] = [r for r in s['required'] if r not in hidden]
    return s


def methods(cls, s: dict) -> dict:
    """Inject @expose_route method signatures."""
    s['methods'] = cls.__pybend_methods_json_signature__()
    return s


def defs(cls, s: dict) -> dict:
    """Collect referenced models and build $defs with schemas, methods, and $id."""
    referenced_models = collect_all_referenced_models(cls)
    if not referenced_models:
        return s

    if '$defs' not in s:
        s['$defs'] = {}

    for model in referenced_models:
        ref_schema = model.referenced_json_schema()
        ref_methods = model.__pybend_methods_json_signature__()
        defs_from_ref = ref_schema.pop('$defs', {})
        s['$defs'] = {**defs_from_ref, **s['$defs']} if defs_from_ref else s['$defs']

        if 'properties' in ref_schema:
            s['$defs'][model.__name__] = ref_schema
        elif model.__name__ not in s['$defs']:
            s['$defs'][model.__name__] = ref_schema

        if model.__name__ in s['$defs']:
            s['$defs'][model.__name__]['methods'] = ref_methods

    for model in referenced_models:
        if model.__name__ in s['$defs']:
            s['$defs'][model.__name__]['$id'] = f"{config.API_URL}/{model.__name__}"

    return s


def access(cls, s: dict) -> dict:
    """Serialize ABAC rules into schema (top-level + $defs)."""
    from pybend.core.authorize.schema import access_schema
    s['access'] = access_schema(cls)

    if '$defs' in s:
        for model in collect_all_referenced_models(cls):
            if model.__name__ in s['$defs']:
                s['$defs'][model.__name__]['access'] = access_schema(model)
    return s


def ui(cls, s: dict) -> dict:
    """Inject UI hints: field exclusion, protected fields, __ui__ config.
    Handles both top-level and $defs."""
    from pybend.core.models.proto_model import _apply_field_exclusion

    # Field exclusion + protected fields (top-level)
    _apply_field_exclusion(s)
    protected = getattr(cls, '__protected_fields__', set())
    if protected and 'properties' in s:
        for field_name in protected:
            if field_name in s['properties']:
                s['properties'][field_name].setdefault('ui', {})['protected'] = True

    # __ui__ config (top-level)
    ui_config = getattr(cls, '__ui__', None)
    if ui_config:
        s['ui'] = dict(ui_config)
        method_ui = ui_config.get('methods', {})
        for method_name, hints in method_ui.items():
            if method_name in s.get('methods', {}):
                s['methods'][method_name]['ui'] = dict(hints)

    # $defs: field exclusion, protected, __ui__
    if '$defs' in s:
        for def_schema in s['$defs'].values():
            _apply_field_exclusion(def_schema)

        for model in collect_all_referenced_models(cls):
            if model.__name__ not in s['$defs']:
                continue
            # Protected fields
            ref_protected = getattr(model, '__protected_fields__', set())
            if ref_protected:
                def_props = s['$defs'][model.__name__].get('properties', {})
                for field_name in ref_protected:
                    if field_name in def_props:
                        def_props[field_name].setdefault('ui', {})['protected'] = True
            # __ui__
            ref_ui = getattr(model, '__ui__', None)
            if ref_ui:
                s['$defs'][model.__name__]['ui'] = dict(ref_ui)
                ref_method_ui = ref_ui.get('methods', {})
                def_methods = s['$defs'][model.__name__].get('methods', {})
                for method_name, hints in ref_method_ui.items():
                    if method_name in def_methods:
                        def_methods[method_name]['ui'] = dict(hints)
    return s


def metadata(cls, s: dict) -> dict:
    """Stamp $schema and $id."""
    s['$schema'] = f"{config.API_URL}/Schema"
    s['$id'] = f"{config.API_URL}/{cls.__name__}"
    return s
