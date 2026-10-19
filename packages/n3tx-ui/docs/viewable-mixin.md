# ViewableMixin and model UI hints

`n3tx_ui` registers a Python model capability and a schema extension on import.
The capability owns HTML view routes; core still owns models/data routes.

```text
import n3tx_ui
  -> register_mixin('__viewable__', ViewableMixin, also_if=['__ui__'])
  -> register viewable schema stage after core ui stage
       |
define model -> capability injection -> register model/routes
       |
schema() -> ui hints     GET /Model/@ -> browser component shell
```

## Declaration

Complete model declaration; pass this class to the application's `create_app`.
The read policy here is public for demonstration; write policy must be chosen
for the application. This is not a complete authentication tutorial.

```python
import n3tx_ui
from pydantic import Field
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED

class Issue(ProtoModel):
    __tablename__ = 'issues'
    __storable__ = True
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED,
                  'update': AUTHENTICATED, 'delete': AUTHENTICATED}
    __ui__ = {
        'field_order': ['title', 'description'],
        'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
    }
    title: str = Field(min_length=1)
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
```

`__viewable__ = True` explicitly opts in; a truthy `__ui__` also triggers
injection. Import before model definition, not merely before app build. A late
import registers the schema stage globally and can emit hints on a later schema
generation, but does **not** retroactively inject the mixin into existing classes.
Invalidating a schema cache is not a repair for missing capability injection.

## UI hints and consumers

The stage copies `__ui__` into schema `ui`, including related `$defs`; it copies
method hints into matching `methods[name].ui`. Extra keys can pass through, but
passing through is not proof that any frontend consumes them.

| Hint | Consumer/effect |
|---|---|
| `field_order`, `groups` | Formidable ordering and fieldsets |
| `renderer.item`, `renderer.detail` | Default entity tag selection |
| `renderer.page`, `renderer.list`, named keys | Collection/default/named route views |
| `icon` | Shared icon token resolver |
| `description`, `create_label` | Default collection header copy |
| `populate.depth` | List/entity read depth hint |
| `methods[name].layout` | `fieldset`, `inline`, `button` method presentation |
| `methods[name].attach_to` | Method placement after a field, not mutation behavior |
| `methods[name].icon`, `count_field`, `button_label`, `placeholder`, `widget` | Method control presentation |

Per-field `json_schema_extra` can carry `ui.widget`, `ui.config`, `ui.display`,
`ui.placeholder` and access hints. The [form guide](formidable.md) describes actual
filtering and validation limitations. Model/action rules are enforced at backend
boundaries; UI metadata alone does not protect data.

## HTML view routes

| GET route | Mount |
|---|---|
| `/Issue/@` | Default collection: `renderer.page -> renderer.list -> ntx-list` |
| `/Issue/@table` | `renderer.table`, otherwise `ntx-table` |
| `/Issue/1/@` | Default member: `renderer.detail -> renderer.item -> ntx-item` |
| `/Issue/1/@detail` | Declared detail/item fallback |
| `/Issue/1/@chat` | Declared chat tag, otherwise `ntx-chat` (requires agents assets) |

Named views resolve `renderer[view]` first. Known collection fallbacks are list
and table; known member fallbacks are item, detail and chat. Unknown names return
400. Tokens match `[A-Za-z0-9][A-Za-z0-9_-]*`; renderer tags must match the safe
custom-element grammar `[a-z][a-z0-9]*(-[a-z0-9]+)+`.

These hidden-from-OpenAPI routes return **minimal HTML shells**, not server-rendered
records. They import `/core/NTT.js`, the base renderer and
`/components/{resolved-tag}.js`. App renderers must exist at that conventional
module path and import their own dependencies. The shells do not include the
full app theme/navigation/auth UI. Record requests made by the shell still pass
through backend authorization; serving the shell is not proof that a record
exists or that the caller may read it.

Do not confuse HTTP `/Issue/@` with client hash `#Issue/@`. Both use semantic view
resolution, but the hash route mounts inside the existing app shell; see
[routing](../../../docs/frontend/COMPONENTS.md#routing).

## Reference

Python callable surface (existing APIs, not changes):

```text
get_static_dir() -> Path
ViewableMixin.register_view_routes(router, *, tag: str) -> None
resolve_collection_view_tag(model_class: type, view: str | None = None) -> str
resolve_member_view_tag(model_class: type, view: str | None = None) -> str
```

[Registration source](../src/n3tx_ui/__init__.py) ·
[Mixin, schema stage and route helpers](../src/n3tx_ui/mixin.py) ·
[Application bootstrap](../../n3tx-core/docs/app-bootstrap.md).
