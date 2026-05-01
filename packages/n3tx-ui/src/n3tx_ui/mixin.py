"""ViewableMixin — injected into models with __viewable__ = True (or __ui__ set).

Owns the __ui__ schema pipeline extension for frontend rendering config.

Injection is automatic via proto_model's register_mixin() call in n3tx_ui/__init__.py:
    __viewable__ = True    → explicit opt-in
    __ui__ = {...}         → guardrail: auto-sets __viewable__ = True
"""
from html import escape
import re
from typing import ClassVar, Optional

from fastapi import HTTPException
from fastapi.responses import HTMLResponse


VIEW_TOKEN_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
TAG_RE = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)+$')


def html_attr(value: object) -> str:
    """Escape a value for safe insertion into an HTML attribute."""
    return escape(str(value), quote=True)


def validate_view_token(view: str | None) -> str | None:
    """Validate a named view token from a route segment.

    ``None`` represents the default ``@`` route and is valid. Empty strings and
    unsafe named tokens are invalid.
    """
    if view is None:
        return None
    if not isinstance(view, str) or not VIEW_TOKEN_RE.fullmatch(view):
        raise ValueError('Invalid view name')
    return view


def validate_component_tag(tag: str) -> str:
    """Validate a custom-element tag before injecting it into HTML."""
    if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
        raise ValueError('Invalid renderer tag')
    return tag


def component_module_url(tag: str) -> str:
    """Return the conventional static module URL for a component tag."""
    return f"/components/{validate_component_tag(tag)}.js"


def render_module_scripts(*tags: str) -> str:
    """Render stable, de-duplicated module imports for component tags."""
    seen = set()
    scripts = []
    for tag in tags:
        url = component_module_url(tag)
        if url in seen:
            continue
        seen.add(url)
        scripts.append(f'    <script type="module" src="{html_attr(url)}"></script>')
    return '\n'.join(scripts)


def _http_error(error: ValueError) -> HTTPException:
    message = str(error)
    if message not in {'Invalid view name', 'Unknown view name', 'Invalid renderer tag'}:
        message = 'Invalid view name'
    return HTTPException(status_code=400, detail=message)


def _schema_renderer(renderer: dict, view: str | None) -> str | None:
    if view and renderer.get(view):
        return validate_component_tag(renderer[view])
    return None


def resolve_collection_view_tag(model_class: type, view: str | None = None) -> str:
    """Resolve the default collection view tag for a model.

    The backend uses the same policy as the frontend router:
    ``renderer[view]`` → known framework fallback → reject unknown views for
    named views, and ``renderer.page`` → ``renderer.list`` → ``ntx-list`` for
    the default collection view.
    """
    renderer = (getattr(model_class, '__ui__', None) or {}).get('renderer', {})
    view = validate_view_token(view)
    declared = _schema_renderer(renderer, view)
    if declared:
        return declared
    if view:
        known = {'list': 'ntx-list', 'table': 'ntx-table'}
        if view in known:
            return known[view]
        raise ValueError('Unknown view name')
    if renderer.get('page'):
        return validate_component_tag(renderer['page'])
    if renderer.get('list'):
        return validate_component_tag(renderer['list'])
    return 'ntx-list'


def render_collection_view(model_class: type, view: str | None = None) -> HTMLResponse:
    """Return a minimal HTML shell for a model collection default view.

    This intentionally bootstraps the normal frontend component system instead
    of introducing server-side component rendering.
    """
    try:
        tag = validate_component_tag(resolve_collection_view_tag(model_class, view))
    except ValueError as error:
        raise _http_error(error)
    model_name = html_attr(model_class.__name__)
    scripts = render_module_scripts('ntx-list', tag)
    html = f"""<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <title>{model_name}</title>
    <script type=\"module\" src=\"/core/NTT.js\"></script>
{scripts}
</head>
<body>
    <{tag} model=\"{model_name}\"></{tag}>
</body>
</html>"""
    return HTMLResponse(html)


def resolve_member_view_tag(model_class: type, view: str | None = None) -> str:
    """Resolve the member view tag for a model.

    The backend mirrors the frontend member resolver: named views first consult
    ``renderer[view]``, then known member fallbacks, then reject unknown views.
    The default member view remains
    ``renderer.detail`` → ``renderer.item`` → ``ntx-item``.
    """
    renderer = (getattr(model_class, '__ui__', None) or {}).get('renderer', {})
    view = validate_view_token(view)
    declared = _schema_renderer(renderer, view)
    if declared:
        return declared
    if view:
        known = {
            'item': validate_component_tag(renderer['item']) if renderer.get('item') else 'ntx-item',
            'detail': (
                validate_component_tag(renderer['detail']) if renderer.get('detail')
                else validate_component_tag(renderer['item']) if renderer.get('item')
                else 'ntx-item'
            ),
            'chat': 'ntx-chat',
        }
        if view in known:
            return known[view]
        raise ValueError('Unknown view name')
    if renderer.get('detail'):
        return validate_component_tag(renderer['detail'])
    if renderer.get('item'):
        return validate_component_tag(renderer['item'])
    return 'ntx-item'


def render_member_view(model_class: type, id: int, view: str | None = None) -> HTMLResponse:
    """Return a minimal HTML shell for a model member view."""
    try:
        tag = validate_component_tag(resolve_member_view_tag(model_class, view))
    except ValueError as error:
        raise _http_error(error)
    ref = html_attr(f'{model_class.__name__}/{id}')
    title = html_attr(model_class.__name__)
    scripts = render_module_scripts('ntx-item', tag)
    html = f"""<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <title>{title}</title>
    <script type=\"module\" src=\"/core/NTT.js\"></script>
{scripts}
</head>
<body>
    <{tag} ref=\"{ref}\" display=\"lg\"></{tag}>
</body>
</html>"""
    return HTMLResponse(html)


class ViewableMixin:
    """Mixin providing frontend UI configuration to models.

    Adds the __ui__ schema extension: emits ui config into schema['ui'] for
    consumption by ntx-list, ntx-item, and Formidable.
    """
    __ui__: ClassVar[Optional[dict]] = None

    @classmethod
    def register_view_routes(cls, router, *, tag: str) -> None:
        """Register HTML/view routes owned by the viewable capability.

        Registers collection view routes:
        ``GET /{ClassName}/@`` and ``GET /{ClassName}/@{view}``.
        Also registers the member default view route:
        ``GET /{ClassName}/{id:int}/@``.
        And the named member view route:
        ``GET /{ClassName}/{id:int}/@{view}``.
        """

        @router.get(f"/{cls.__name__}/@", tags=[tag], include_in_schema=False)
        async def collection_default_view(_cls=cls):
            return render_collection_view(_cls)

        @router.get(f"/{cls.__name__}/@{{view}}", tags=[tag], include_in_schema=False)
        async def collection_named_view(view: str, _cls=cls):
            return render_collection_view(_cls, view=view)

        @router.get(f"/{cls.__name__}/{{id:int}}/@", tags=[tag], include_in_schema=False)
        async def member_default_view(id: int, _cls=cls):
            return render_member_view(_cls, id=id)

        @router.get(f"/{cls.__name__}/{{id:int}}/@{{view}}", tags=[tag], include_in_schema=False)
        async def member_named_view(id: int, view: str, _cls=cls):
            return render_member_view(_cls, id=id, view=view)


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
