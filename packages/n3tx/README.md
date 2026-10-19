# n3tx Meta-Package

`n3tx` installs the N3TX package family. It is an installation convenience, not a
second model or application runtime.

## Installation

In a Python 3.10+ virtual environment:

```bash
python -m pip install n3tx
```

For a smaller API/UI app, install only `n3tx-core n3tx-ui`. For a complete
application example, follow [Getting started](../../docs/GETTING_STARTED.md).

## Package Landscape

| Package | Purpose |
|---|---|
| [Core](../n3tx-core/README.md) | Models, storage, schema, auth, HTTP and JS runtime |
| [UI](../n3tx-ui/README.md) | Components, forms, widgets and view shells |
| [Actors](../n3tx-actors/README.md) | Messaging and network adapters |
| [Agents](../n3tx-agents/README.md) | Agent configuration, execution and tools |
| [Files](../n3tx-files/README.md) | File metadata and byte stores |

## Re-export Map

The import namespace is `n3tx_meta`, not `n3tx`. Its initializer star-imports
core, actors and files; agent exports are attempted with an ImportError fallback.
It does not explicitly import UI. Prefer direct imports so capability ownership
and initialization order are clear:

```python
import n3tx_ui  # before defining models that opt into __ui__
from n3tx_core.app import create_app, N3TXApp
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.base_user import BaseUser
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.utils.decorators import expose_route
```

Import `n3tx_agents` before defining models with `__agent__`. Installing packages
does not configure providers, authorize tools, or grant file access.

## Key Patterns

Construction (`create_app`, builder, raw setup) is separate from HTTP routing
(`direct` or `actor`). Fields and validators remain model-owned; native CRUD
handles ordinary edits, while exposed methods express domain operations.
Neither action exposure nor storage replacement implies atomicity.

Configuration, security defaults, migration requirements and verification are
documented in [Operations](../../docs/OPERATIONS.md). The
[documentation index](../../docs/README.md) is the canonical navigation map.

## License

[MIT](../../LICENSE).
