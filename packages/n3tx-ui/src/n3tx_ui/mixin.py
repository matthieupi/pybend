"""ViewableMixin — injected into models with __viewable__ = True (or __ui__ set).

Owns the __ui__ schema pipeline extension for frontend rendering config.

Injection is automatic via proto_model's register_mixin() call in n3tx_ui/__init__.py:
    __viewable__ = True    → explicit opt-in
    __ui__ = {...}         → guardrail: auto-sets __viewable__ = True
"""
from typing import ClassVar, Optional


class ViewableMixin:
    """Mixin providing frontend UI configuration to models.

    Adds the __ui__ schema extension: emits ui config into schema['ui'] for
    consumption by ntx-list, ntx-item, and Formidable.
    """
    __ui__: ClassVar[Optional[dict]] = None


# ── Schema extension ──────────────────────────────────────────────────────
# Registered as side-effect when this module is imported.

from n3tx_core.models.proto_schema import schema_extension
from n3tx_core.utils.introspection import collect_all_referenced_models


@schema_extension(after='ui')
def viewable(cls, s: dict) -> dict:
    """Emit __ui__ class config into schema. No-op for non-viewable models."""
    ui_config = getattr(cls, '__ui__', None)
    if not ui_config:
        return s

    s['ui'] = dict(ui_config)
    for method_name, hints in ui_config.get('methods', {}).items():
        if method_name in s.get('methods', {}):
            s['methods'][method_name]['ui'] = dict(hints)

    # $defs: emit __ui__ for referenced models that also have it
    for model in collect_all_referenced_models(cls):
        if model.__name__ not in s.get('$defs', {}):
            continue
        ref_ui = getattr(model, '__ui__', None)
        if ref_ui:
            s['$defs'][model.__name__]['ui'] = dict(ref_ui)
            for method_name, hints in ref_ui.get('methods', {}).items():
                def_methods = s['$defs'][model.__name__].get('methods', {})
                if method_name in def_methods:
                    def_methods[method_name]['ui'] = dict(hints)
    return s
