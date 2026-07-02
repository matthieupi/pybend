"""Reference primitives for N3TX models.

`Ref[T]` is the typed identity pointer primitive. Historically it represented
an integer FK in the local database; distributed N3TX extends that meaning to a
string address Matrix can resolve, while preserving local integer behavior.
"""

from __future__ import annotations

from typing import Annotated, Any, Generic, Optional, TypeVar, get_args
from urllib.parse import urlparse

from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


T = TypeVar("T", bound=BaseModel)


class _SelfRefMarker:
    """Metadata tag to identify Ref['self'] fields during schema generation and migration."""
    pass


def _api_url(api_url: str | None = None) -> str:
    if api_url:
        return api_url.rstrip('/')
    try:
        from n3tx_core import config
        return getattr(config, 'API_URL', '').rstrip('/')
    except Exception:
        return ''


def _configured_remotes(remotes=None) -> dict:
    if remotes is not None:
        return remotes or {}
    try:
        from n3tx_core import config
        return getattr(config, 'REMOTES', {}) or {}
    except Exception:
        return {}


def _remote_url(entry) -> str | None:
    if isinstance(entry, str):
        return entry.rstrip('/')
    if isinstance(entry, dict):
        url = entry.get('url') or entry.get('base_url')
        return url.rstrip('/') if isinstance(url, str) else None
    return None


def _target_name(target_cls=None) -> str | None:
    return getattr(target_cls, '__name__', None) if target_cls is not None else None


def _parse_http_ref(value: str, *, api_url=None, remotes=None) -> tuple[str | None, str | None, str | None, bool]:
    """Return (service, class_name, id, is_current_service) for known HTTP refs."""
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return None, None, None, False

    candidate_base = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
    current = _api_url(api_url)
    if current and candidate_base == current:
        try:
            service, class_name, ident = parse_ref_string(parsed.path)
        except ValueError:
            return None, None, None, False
        return service, class_name, ident, True

    for name, entry in _configured_remotes(remotes).items():
        remote_base = _remote_url(entry)
        if remote_base and candidate_base == remote_base:
            try:
                _service, class_name, ident = parse_ref_string(parsed.path)
            except ValueError:
                return None, None, None, False
            return name, class_name, ident, False

    return None, None, None, False


def is_distributed_ref(value: object) -> bool:
    """Return True for canonical ``n3tx://service/ClassName/id`` refs."""
    if not isinstance(value, str):
        return False
    try:
        service, class_name, ident = parse_ref_string(value)
    except ValueError:
        return False
    return bool(service and class_name and ident)


def is_external_link(value: object, *, remotes=None) -> bool:
    """Return True for URLs that are not configured N3TX refs."""
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return False
    service, class_name, ident, is_current = _parse_http_ref(value, remotes=remotes)
    return not (is_current or (service and class_name and ident))


def parse_ref_string(value: str) -> tuple[str | None, str | None, str | None]:
    """Parse a canonical distributed ref or local class-name path.

    Returns ``(service, class_name, id)``. ``service`` is ``None`` for local
    refs such as ``/File/12``. This deliberately returns a primitive tuple — an
    address is a string, not a public address object.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Reference address must be a non-empty string")

    value = value.strip()
    if value.startswith('n3tx://'):
        parsed = urlparse(value)
        parts = [part for part in parsed.path.split('/') if part]
        if parsed.scheme != 'n3tx' or not parsed.netloc or len(parts) != 2:
            raise ValueError(f"Invalid distributed reference: {value!r}")
        return parsed.netloc, parts[0], parts[1]

    if value.startswith('/'):
        parts = [part for part in value.split('/') if part]
        if len(parts) != 2:
            raise ValueError(f"Invalid local reference: {value!r}")
        return None, parts[0], parts[1]

    raise ValueError(f"Unsupported reference address: {value!r}")


def _parse_id(value: object) -> int | None:
    try:
        ident = int(value)
    except (TypeError, ValueError):
        return None
    return ident if ident >= 0 else None


def _matches_target(class_name: str | None, target_cls=None) -> bool:
    target_name = _target_name(target_cls)
    return not target_name or not class_name or class_name == target_name


def local_ref_id(value, *, target_cls=None, api_url=None, remotes=None) -> int | None:
    """Return the local integer id if ``value`` points at this service."""
    if isinstance(value, Ref):
        return local_ref_id(value.id, target_cls=target_cls, api_url=api_url, remotes=remotes)
    if isinstance(value, BaseModel):
        return _parse_id(getattr(value, 'id', None))
    if isinstance(value, int):
        return _parse_id(value)
    if isinstance(value, dict):
        return local_ref_id(value.get('id') or value.get('$id'), target_cls=target_cls, api_url=api_url, remotes=remotes)
    if not isinstance(value, str):
        return None

    value = value.strip()
    if value.startswith('/'):
        _service, class_name, ident = parse_ref_string(value)
        return _parse_id(ident) if _matches_target(class_name, target_cls) else None
    if value.startswith('n3tx://'):
        return None
    parsed = urlparse(value)
    if parsed.scheme in {'http', 'https'}:
        service, class_name, ident, is_current = _parse_http_ref(value, api_url=api_url, remotes=remotes)
        if is_current and _matches_target(class_name, target_cls):
            return _parse_id(ident)
        return None
    return _parse_id(value)


def canonicalize_ref(value, *, target_cls=None, api_url=None, remotes=None) -> str | int | None:
    """Canonicalize local or distributed refs for storage.

    Local refs become integer ids where possible. Configured remote HTTP(S)
    refs become ``n3tx://service/ClassName/id``. Canonical ``n3tx://`` refs are
    preserved. External links are returned unchanged so callers can classify or
    reject them according to context.
    """
    if value is None:
        return None
    if isinstance(value, Ref):
        return canonicalize_ref(value.id, target_cls=target_cls, api_url=api_url, remotes=remotes)
    if isinstance(value, BaseModel):
        return _parse_id(getattr(value, 'id', None))
    if isinstance(value, int):
        return _parse_id(value)
    if isinstance(value, dict):
        return canonicalize_ref(value.get('id') or value.get('$id'), target_cls=target_cls, api_url=api_url, remotes=remotes)
    if not isinstance(value, str):
        return value

    value = value.strip()
    if value.startswith('n3tx://'):
        service, class_name, ident = parse_ref_string(value)
        if not _matches_target(class_name, target_cls):
            raise ValueError(f"Reference target mismatch: {value!r}")
        return f"n3tx://{service}/{class_name}/{ident}"
    if value.startswith('/'):
        _service, class_name, ident = parse_ref_string(value)
        if not _matches_target(class_name, target_cls):
            raise ValueError(f"Reference target mismatch: {value!r}")
        return _parse_id(ident)

    parsed = urlparse(value)
    if parsed.scheme in {'http', 'https'}:
        service, class_name, ident, is_current = _parse_http_ref(value, api_url=api_url, remotes=remotes)
        if is_current:
            if not _matches_target(class_name, target_cls):
                raise ValueError(f"Reference target mismatch: {value!r}")
            return _parse_id(ident)
        if service and class_name and ident:
            if not _matches_target(class_name, target_cls):
                raise ValueError(f"Reference target mismatch: {value!r}")
            return f"n3tx://{service}/{class_name}/{ident}"
        return value

    ident = _parse_id(value)
    if ident is not None:
        return ident
    raise ValueError(f"Unsupported reference address: {value!r}")


def public_ref(value, *, target_cls=None, api_url=None, remotes=None) -> str | None:
    """Return the response-facing ref string for a local or distributed ref."""
    if value is None:
        return None
    if is_distributed_ref(value):
        return str(value)
    canonical = canonicalize_ref(value, target_cls=target_cls, api_url=api_url, remotes=remotes)
    if isinstance(canonical, int):
        class_name = _target_name(target_cls) or ''
        base = _api_url(api_url)
        return f"{base}/{class_name}/{canonical}" if class_name else f"{base}/{canonical}"
    if isinstance(canonical, str) and is_distributed_ref(canonical):
        return canonical
    return str(canonical) if canonical is not None else None


def flatten_refs(obj: BaseModel) -> dict:
    """Recursively flatten Ref values for storage/validation."""
    flat = obj.model_dump()
    for field, value in flat.items():
        if isinstance(value, Ref):
            flat[field] = value.model_dump()
        elif isinstance(value, BaseModel):
            flat[field] = flatten_refs(value)
        elif isinstance(value, list):
            flat[field] = [
                v.model_dump() if isinstance(v, Ref) else v for v in value
            ]
    return flat


class Ref(Generic[T]):
    """Typed model/actor identity pointer."""

    def __class_getitem__(cls, params):
        if params == 'self':
            return Annotated[int, _SelfRefMarker()]
        return super().__class_getitem__(params)

    def __init__(self, value: Optional[Any] = None):
        if isinstance(value, BaseModel):
            self.id = getattr(value, 'id', None)
            self._model = value
        elif isinstance(value, int):
            self.id = value
            self._model = None
        elif isinstance(value, dict):
            self.id = canonicalize_ref(value.get('id') or value.get('$id'))
            self._model = None
        elif isinstance(value, str):
            try:
                canonical = canonicalize_ref(value)
            except ValueError as exc:
                raise ValueError(f"Invalid FK assignment: {value}") from exc
            if is_external_link(canonical):
                raise ValueError(f"Invalid FK assignment: {value}")
            self.id = canonical
            self._model = None
        else:
            raise ValueError(f"Invalid FK assignment: {value}")

    def __int__(self):
        if not isinstance(self.id, int):
            raise TypeError(f"Cannot coerce distributed Ref to int: {self.id}")
        return self.id

    def __repr__(self):
        return str(self.id)

    def __str__(self):
        return f"<Ref id={self.id}>"

    def __json__(self):
        return self.id

    def model_dump(self):
        return self.id

    def to_python(self, *args, **kwargs):
        return self.id

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            python_schema=core_schema.no_info_plain_validator_function(
                lambda v: v if isinstance(v, str) else (v.model_dump() if isinstance(v, Ref) else v)
            ),
            json_schema=core_schema.int_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: v if isinstance(v, str) else (v.model_dump() if isinstance(v, Ref) else (int(v) if v is not None else None))
            )
        )

    @classmethod
    def validate(cls, v):
        return cls(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: core_schema.CoreSchema, handler) -> JsonSchemaValue:
        args = get_args(cls)
        if not args:
            return {"type": "integer"}
        target = args[0]
        if not isinstance(target, type) or not issubclass(target, BaseModel):
            return {"type": "integer"}
        return {"type": "$ref", "$ref": f"#/$defs/{target.__name__}"}


__all__ = [
    'Ref', '_SelfRefMarker', 'flatten_refs',
    'is_distributed_ref', 'is_external_link', 'parse_ref_string',
    'canonicalize_ref', 'local_ref_id', 'public_ref',
]
