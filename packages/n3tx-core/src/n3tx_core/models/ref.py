"""Web-native reference values for N3TX models.

``Ref[T]`` is an absolute HTTP(S) entity URL. Local model relationships use
``T``/``list[T]`` and compact database ids; refs stay globally resolvable URL
strings until an explicit hydration request is made.
"""

from __future__ import annotations

from typing import Annotated, Any, Generic, TypeVar, get_args
from urllib.parse import unquote, urlsplit, urlunsplit

from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


T = TypeVar("T", bound=BaseModel)


class _SelfRefMarker:
    """Identify historical ``Ref['self']`` local parent-id fields."""


def _api_url(api_url: str | None = None) -> str:
    if api_url:
        return api_url.rstrip("/")
    try:
        from n3tx_core import config

        return getattr(config, "API_URL", "").rstrip("/")
    except Exception:
        return ""


def _parts(value: object) -> tuple[str, str, str, str]:
    """Return ``(url, base_url, schema, id)`` for an entity URL."""
    if isinstance(value, dict):
        value = value.get("$id")
    elif isinstance(value, BaseModel):
        value = value.model_response().get("$id") if hasattr(value, "model_response") else None

    if not isinstance(value, str):
        raise TypeError("Reference must be an absolute HTTP(S) entity URL string")

    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Reference must be an absolute HTTP(S) entity URL")
    if parsed.query or parsed.fragment:
        raise ValueError("Reference entity URLs cannot contain a query or fragment")

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        raise ValueError("Reference URL must end with /{Schema}/{id}")

    schema, ident = map(unquote, segments[-2:])
    if not schema or not ident or "/" in schema or "/" in ident:
        raise ValueError("Reference URL must contain valid schema and id segments")

    base_path = "/" + "/".join(segments[:-2]) if len(segments) > 2 else ""
    base_url = urlunsplit((parsed.scheme, parsed.netloc, base_path, "", "")).rstrip("/")
    canonical = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
    return canonical, base_url, schema, ident


def is_ref_url(value: object) -> bool:
    """Return whether ``value`` is a valid absolute entity URL."""
    try:
        _parts(value)
    except (TypeError, ValueError):
        return False
    return True


def _target_name(target_cls=None) -> str | None:
    return getattr(target_cls, "__name__", None) if target_cls is not None else None


def _validated_url(value: object, target_cls=None) -> str:
    url, _base_url, schema, _ident = _parts(value)
    target_name = _target_name(target_cls)
    if target_name and schema != target_name:
        raise ValueError(f"Reference target mismatch: expected {target_name}, got {schema}")
    return url


def _storage_id(value: object) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            ident = int(value)
        except ValueError:
            return value
        return ident if ident >= 0 else None
    return None


def local_ref_id(value, *, target_cls=None, api_url=None, remotes=None) -> int | str | None:
    """Extract a local relationship id without performing remote I/O.

    Raw ids remain supported for ``T``/``list[T]`` storage normalization. URL
    values are local only when their parsed base URL equals ``api_url``.
    ``remotes`` is accepted temporarily for call-site compatibility and ignored.
    """
    if isinstance(value, BaseModel):
        return _storage_id(getattr(value, "id", None))
    if isinstance(value, dict):
        return local_ref_id(
            value.get("id") or value.get("$id"), target_cls=target_cls, api_url=api_url
        )
    if isinstance(value, Ref):
        value = str(value)
    if isinstance(value, (int, str)) and not is_ref_url(value):
        if isinstance(value, str) and ("://" in value or value.startswith("/")):
            return None
        return _storage_id(value)

    try:
        _url, base_url, schema, ident = _parts(value)
    except (TypeError, ValueError):
        return None
    if base_url != _api_url(api_url):
        return None
    if _target_name(target_cls) not in (None, schema):
        return None
    return _storage_id(ident)


def local_id_from_ref_url(value, *, target_cls=None, api_url=None) -> int | str | None:
    """Return the id when an entity URL belongs to the current API."""
    return local_ref_id(value, target_cls=target_cls, api_url=api_url)


def public_id_url(value, *, target_cls=None, api_url=None) -> str:
    """Build or validate the canonical public URL for an entity identity."""
    if is_ref_url(value):
        return _validated_url(value, target_cls)
    if isinstance(value, BaseModel):
        value = getattr(value, "id", None)
    elif isinstance(value, dict):
        value = value.get("id") or value.get("$id")
    ident = _storage_id(value)
    target_name = _target_name(target_cls)
    base = _api_url(api_url)
    if ident is None or not target_name or not base:
        raise ValueError("A local id, target class, and API URL are required")
    return f"{base}/{target_name}/{ident}"


class Ref(str, Generic[T]):
    """Validated, immutable HTTP(S) identity URL for ``T``."""

    _target_cls = None

    def __new__(cls, value: object, *, target_cls=None):
        url = _validated_url(value, target_cls)
        instance = str.__new__(cls, url)
        instance._target_cls = target_cls
        return instance

    def __setattr__(self, name, value):
        # ``typing`` assigns ``__orig_class__`` after ``Ref[T](...)`` returns.
        if name == "__orig_class__":
            args = get_args(value)
            target_cls = args[0] if args and isinstance(args[0], type) else None
            _validated_url(self, target_cls)
            object.__setattr__(self, "_target_cls", target_cls)
        object.__setattr__(self, name, value)

    @classmethod
    def __class_getitem__(cls, params):
        if params == "self":
            return Annotated[int, _SelfRefMarker()]
        return super().__class_getitem__(params)

    @classmethod
    def url(cls, value: object) -> str:
        return _validated_url(value)

    @classmethod
    def base_url(cls, ref: str) -> str:
        return _parts(ref)[1]

    @classmethod
    def schema(cls, ref: str) -> str:
        return _parts(ref)[2]

    @classmethod
    def id(cls, ref: str) -> str:
        return _parts(ref)[3]

    def hydrate(self, *, user=None, context=None) -> T:
        """Explicitly resolve this ref without changing its URL value."""
        resolver = context
        if isinstance(context, dict):
            resolver = context.get("reference_resolver") or context.get("resolver")
        elif context is not None and not callable(context) and not hasattr(context, "resolve"):
            resolver = getattr(context, "reference_resolver", None) or getattr(context, "resolver", None)
        if resolver is None:
            raise RuntimeError("Ref.hydrate() requires an explicit resolver context")
        resolve = getattr(resolver, "resolve", resolver)
        if not callable(resolve):
            raise TypeError("Reference resolver must be callable or expose resolve()")
        return resolve(str(self), target_cls=self._target_cls, user=user, context=context)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        args = get_args(source_type)
        target_cls = args[0] if args and isinstance(args[0], type) else None

        return core_schema.no_info_after_validator_function(
            lambda value: value if isinstance(value, cls) and value._target_cls is target_cls else cls(value, target_cls=target_cls),
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
            metadata={"x-ref-target": _target_name(target_cls)},
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler
    ) -> JsonSchemaValue:
        target = (schema.get("metadata") or {}).get("x-ref-target")
        result = {"type": "string", "format": "uri"}
        if target:
            result["x-ref"] = target
        return result


def flatten_refs(obj: BaseModel) -> dict:
    """Dump a model recursively with refs represented as URL strings."""
    return obj.model_dump(mode="python")


__all__ = [
    "Ref",
    "_SelfRefMarker",
    "flatten_refs",
    "is_ref_url",
    "local_ref_id",
    "local_id_from_ref_url",
    "public_id_url",
]
