"""
Populate spec parser for eager loading of related entities.

Parses ?populate= and ?depth= query parameters into a structured spec
that drives batch loading in the storage layer.

Examples:
    parse_populate("comments", None)
        → PopulateSpec(fields={"comments": PopulateSpec()})

    parse_populate(None, 1)
        → PopulateSpec(depth=1)

    parse_populate("comments.likes", 1)
        → PopulateSpec(depth=1, fields={"comments": PopulateSpec(fields={"likes": PopulateSpec()})})

    parse_populate("comments,tags", None)
        → PopulateSpec(fields={"comments": PopulateSpec(), "tags": PopulateSpec()})
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger('n3tx.utils')

DEFAULT_CHILD_LIMIT = 20


@dataclass
class PopulateSpec:
    depth: int = 0
    fields: Dict[str, 'PopulateSpec'] = field(default_factory=dict)
    limit: int = DEFAULT_CHILD_LIMIT

    @property
    def is_empty(self) -> bool:
        return self.depth == 0 and not self.fields

    def should_populate(self, field_name: str) -> bool:
        """True if this field should be eagerly loaded."""
        return self.depth > 0 or field_name in self.fields

    def child_spec(self, field_name: str) -> PopulateSpec:
        """Return the PopulateSpec for a child field."""
        explicit = self.fields.get(field_name)
        if explicit:
            # Merge: child gets depth-1 from parent + its own explicit fields
            return PopulateSpec(
                depth=max(self.depth - 1, 0, explicit.depth),
                fields=explicit.fields,
                limit=explicit.limit,
            )
        # Depth-only: decrement
        if self.depth > 0:
            return PopulateSpec(depth=self.depth - 1, limit=self.limit)
        return PopulateSpec()


def parse_populate(populate_param: Optional[str], depth_param: Optional[int]) -> PopulateSpec:
    """Parse query parameters into a PopulateSpec.

    Args:
        populate_param: Comma-separated field paths, e.g. "comments,tags" or "comments.likes"
        depth_param: Max depth for auto-populating all ListRef/Ref fields
    """
    spec = PopulateSpec(depth=depth_param or 0)

    if not populate_param:
        return spec

    for path in populate_param.split(','):
        path = path.strip()
        if not path:
            continue
        parts = path.split('.')
        current = spec
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part not in current.fields:
                current.fields[part] = PopulateSpec()
            current = current.fields[part]

    return spec
