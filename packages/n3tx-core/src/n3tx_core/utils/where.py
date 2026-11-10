"""Compile model field conditions into parameterized SQLite predicates.

API: compile_where validates and binds conditions; query_field checks declared
field names, and parse_where recognizes the shared condition vocabulary.
StorableMixin combines caller predicates with trusted policy SQL. Where rules
use the same compiler with internal public=False; HTTP never exposes that flag.
This module selects rows, not response fields or arbitrary JSON payloads."""

import math
import re
from datetime import date, datetime
from types import UnionType
from typing import Annotated, Literal, Union, get_args, get_origin

from pydantic import AwareDatetime, NaiveDatetime, TypeAdapter


OPERATORS = {
    'lt': '<', 'gt': '>', 'lte': '<=', 'gte': '>=',
    'ne': '!=', 'in': 'IN', 'contains': 'CONTAINS',
}
_IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_]*')


def query_field(model_class, name: str, *, public: bool = True):
    """Return a declared field, denying private names and public secret probes.

    Trusted policies may set public=False for hidden/excluded fields.
    Write protection does not restrict querying. Identifiers and declared-field
    membership are always validated."""
    # 0. Never resolve arbitrary attributes, methods, aliases, or SQL fragments.
    if (
        not isinstance(name, str) or not _IDENTIFIER.fullmatch(name)
        or '__' in name or name not in model_class.model_fields
    ):
        raise ValueError('Invalid or unknown query field')
    field = model_class.model_fields[name]
    # 1. Public selection must not disclose secret values through result counts.
    if public and (
        field.exclude or getattr(field, 'exclude_if', None) is not None
        or name in (getattr(model_class, '__hidden_fields__', ()) or ())
    ):
        raise ValueError('Query field is not public')
    return field


def _is_text(annotation) -> bool:
    """Identify string annotations without treating serialized JSON as text."""
    from n3tx_core.widgets.widget import Widget
    # 0. Unwrap native text widgets and Annotated metadata before type checks.
    if isinstance(annotation, type) and issubclass(annotation, Widget):
        annotation = annotation.base_type
    origin = get_origin(annotation)
    if origin is Annotated:
        return _is_text(get_args(annotation)[0])
    # 1. Permit nullable text and string literals, not arbitrary unions.
    if origin in (Union, UnionType):
        types = [t for t in get_args(annotation) if t is not type(None)]
        return bool(types) and all(_is_text(t) for t in types)
    if origin is Literal:
        return all(isinstance(value, str) for value in get_args(annotation))
    return isinstance(annotation, type) and issubclass(annotation, str)


def parse_where(conditions: dict) -> list:
    """Parse field conditions and OR groups, rejecting unknown operators."""
    # 0. Validate condition keys before interpreting the operator vocabulary.
    if not isinstance(conditions, dict):
        raise ValueError('where must be an object')
    result = []
    for key, value in conditions.items():
        if key == '$or':
            if not isinstance(value, list) or not value or any(
                not isinstance(branch, dict) or not branch for branch in value
            ):
                raise ValueError('$or requires nonempty condition objects')
            result.append((None, 'OR', value))
            continue
        if not isinstance(key, str):
            raise ValueError('where field names must be strings')
        parts = key.split('__')
        if len(parts) == 1:
            field, operator = key, '='
        elif len(parts) == 2 and parts[1] in OPERATORS:
            field, operator = parts[0], OPERATORS[parts[1]]
        else:
            raise ValueError('Unsupported where operator')
        if not _IDENTIFIER.fullmatch(field):
            raise ValueError('Invalid where field name')
        result.append((field, operator, value))
    return result


def compile_where(
    model_class, conditions: dict, *, public: bool = True, _depth: int = 0,
) -> tuple[str, list]:
    """Validate declared fields and compile ANDed, bound scalar predicates.

    Contains is literal and case-sensitive. NULL equality uses IS NULL;
    empty membership matches no rows. Invalid input raises ValueError.
    Only trusted authorization rules should request public=False. Internal
    _depth bounds recursive OR groups to eight levels. Date values use native
    storage representation, without normalizing timezone offsets."""
    # 0. Resolve declared columns; no caller-provided SQL is accepted.
    if _depth > 8:
        raise ValueError('where nesting exceeds eight levels')
    clauses, params = [], []
    for field, operator, value in parse_where(conditions):
        if operator == 'OR':
            branches = []
            for branch in value:
                clause, values = compile_where(
                    model_class, branch, public=public, _depth=_depth + 1,
                )
                branches.append(f'({clause})')
                params.extend(values)
            clauses.append('(' + ' OR '.join(branches) + ')')
            continue
        field_info = query_field(model_class, field, public=public)
        # Qualify identifiers so SQLite cannot treat missing columns as strings.
        table = getattr(model_class, '__tablename__', None)
        column = f'"{field}"'
        if table is not None:
            if not isinstance(table, str) or not re.fullmatch(
                r'[A-Za-z_][A-Za-z0-9_]*', table,
            ):
                raise ValueError('Invalid query table name')
            column = f'"{table}".{column}'
        values = value if operator == 'IN' else [value]
        if operator == 'IN' and not isinstance(value, (list, tuple)):
            raise ValueError('where __in requires a list or tuple')
        # Match native SQLite date storage without normalizing timezones.
        types = get_args(field_info.annotation) or (field_info.annotation,)
        if any(
            t in (date, datetime, AwareDatetime, NaiveDatetime) for t in types
        ):
            adapter = TypeAdapter(field_info.rebuild_annotation())
            values = [
                adapter.validate_python(item) if item is not None else None
                for item in values
            ]
            values = [
                item.isoformat(' ') if isinstance(item, datetime)
                else item.isoformat() if isinstance(item, date) else item
                for item in values
            ]
            if operator != 'IN':
                value = values[0]
        for item in values:
            if item is not None and not isinstance(
                item, (str, int, float, bool),
            ):
                raise ValueError('where values must be scalars')
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError('where numbers must be finite')
            if isinstance(item, int) and not -(2**63) <= item < 2**63:
                raise ValueError('where integer outside SQLite range')
        # 1. Bind values separately from validated column/operator syntax.
        if operator == 'CONTAINS':
            if not _is_text(field_info.annotation):
                raise ValueError('where __contains requires a text field')
            if not isinstance(value, str):
                raise ValueError('where __contains requires a string')
            clauses.append(f'instr({column}, ?) > 0')
            params.append(value)
        elif operator == 'IN':
            if not values:
                clauses.append('1=0')
            else:
                placeholders = ','.join('?' for _ in values)
                clauses.append(f'{column} IN ({placeholders})')
                params.extend(values)
        elif value is None and operator in ('=', '!='):
            comparison = 'IS NULL' if operator == '=' else 'IS NOT NULL'
            clauses.append(f'{column} {comparison}')
        else:
            clauses.append(f'{column} {operator} ?')
            params.append(value)
    return (' AND '.join(clauses) or '1=1', params)


# Changelog
# - 2026-11-02: Share validated predicates and literal text contains queries;
#   restrict public fields and qualify stored columns.
#   Keep write-protected readable fields eligible for filtering and ordering.
# - 2026-11-10: Import the native validated where compiler.
