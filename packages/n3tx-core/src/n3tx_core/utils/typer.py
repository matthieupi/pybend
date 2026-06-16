"""Compatibility exports for reference primitives.

`Ref` now lives with `ListRef` and distributed string helpers in
`n3tx_core.models.ref`. This module remains as the historical import surface.
"""

from n3tx_core.models.ref import Ref, _SelfRefMarker, flatten_refs

__all__ = ['Ref', '_SelfRefMarker', 'flatten_refs']
