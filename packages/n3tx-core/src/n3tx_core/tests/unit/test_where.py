"""Protect shared predicate validation, binding and rule semantics."""

import sqlite3
from datetime import datetime
from enum import Enum
from types import SimpleNamespace
from typing import Annotated, ClassVar, Literal

import pytest
from pydantic import (
    AwareDatetime, BaseModel, Field, PrivateAttr, computed_field,
)

from n3tx_core.authorize import AccessContext, Where
from n3tx_core.utils.where import compile_where, parse_where
from n3tx_core.widgets import CurrencyField, DateTimeField, MarkdownField

pytestmark = pytest.mark.unit


class ConditionRow(BaseModel):
    """Declare the only legal predicate columns."""

    name: str = ''
    score: int | None = None


class TextChoice(str, Enum):
    """Represent a supported string-subclass annotation."""

    OPEN = 'open'


class WidgetQueryRow(BaseModel):
    """Declare native text widgets and nontext fields without app imports."""

    __tablename__: ClassVar[str] = 'widget_query_rows'
    name: str
    bare: MarkdownField
    description: Annotated[MarkdownField, Field(min_length=8)]
    nullable: MarkdownField | None = None
    currency: CurrencyField = 0
    timestamp: DateTimeField | None = None
    payload: dict = Field(default_factory=dict)


class PublicQueryRow(ConditionRow):
    """Expose ordinary fields while keeping secret query inputs private."""

    __tablename__: ClassVar[str] = 'public_query_rows'
    __hidden_fields__: ClassVar[set] = {'hidden'}
    __protected_fields__: ClassVar[set] = {'protected', 'hidden', 'excluded'}
    excluded: str = Field(default='secret', exclude=True)
    conditional: str = Field(default='secret', exclude_if=lambda value: True)
    hidden: str = 'secret'
    protected: str = 'secret'
    aliased: str = Field(default='text', alias='external_name')
    payload: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    nullable: str | None = None
    literal: Literal['open', 'closed'] = 'open'
    choice: TextChoice = TextChoice.OPEN
    mixed: str | int = 'open'
    _private: str = PrivateAttr(default='secret')

    @computed_field
    @property
    def computed(self) -> str:
        """Provide a computed value that is not a stored query column."""
        return self.excluded

    def describe_secret(self) -> str:
        """Provide a method that query validation must never resolve."""
        return self.excluded


@pytest.mark.parametrize(
    'field',
    ['excluded', 'conditional', 'hidden', '_private',
     '__dict__', 'name__class__', 'describe_secret', 'computed',
     'external_name', 'missing', 'name" OR 1=1 --'],
)
def test_public_compiler_rejects_nonpublic_or_nonfield_names(field):
    """Prevent secret probes and arbitrary Python or SQL name resolution."""
    # 0. Rejection must apply even to syntactically valid declared secrets.
    with pytest.raises(ValueError):
        compile_where(PublicQueryRow, {field: 'secret'})


@pytest.mark.parametrize(
    'field', ['excluded', 'conditional', 'hidden'],
)
def test_trusted_policy_can_filter_nonpublic_fields(field):
    """Keep authorization able to restrict records using nonpublic columns."""
    # 0. Resolve a trusted policy against a declared secret column.
    conditions = {field: 'secret'}
    ctx = AccessContext(user={}, action='list', model_class=PublicQueryRow)
    # 1. Policy compilation alone may opt into the nonpublic declaration.
    assert Where(**conditions).sql_filter(ctx) == (
        f'"public_query_rows"."{field}" = ?', ['secret'],
    )
    assert compile_where(PublicQueryRow, conditions, public=False) == (
        Where(**conditions).sql_filter(ctx)
    )


def test_public_compiler_allows_readable_write_protected_field():
    """Write protection must not prevent querying a readable declaration."""
    # 0. Compile protected equality and text matching as ordinary public input.
    equality = compile_where(PublicQueryRow, {'protected': 'secret'})
    contains = compile_where(PublicQueryRow, {'protected__contains': '%_'})
    # 1. Keep identifiers qualified and scalar values separately bound.
    assert equality == ('"public_query_rows"."protected" = ?', ['secret'])
    assert contains == (
        'instr("public_query_rows"."protected", ?) > 0', ['%_'],
    )


@pytest.mark.parametrize(
    'field', ['_private', '__dict__', 'describe_secret', 'computed',
              'external_name', 'missing'],
)
def test_trusted_policy_still_rejects_nonfield_names(field):
    """The trusted escape hatch never authorizes arbitrary identifiers."""
    # 0. Trusted policies still require a declared safe model identifier.
    with pytest.raises(ValueError):
        compile_where(PublicQueryRow, {field: 'x'}, public=False)


@pytest.mark.parametrize('field', ['score', 'payload', 'metadata', 'mixed'])
def test_contains_rejects_numeric_and_json_annotations(field):
    """Do not coerce numeric or serialized JSON columns into text search."""
    # 0. A string needle cannot turn a nontext column into a text field.
    with pytest.raises(ValueError):
        compile_where(PublicQueryRow, {field + '__contains': '1'})


@pytest.mark.parametrize(
    'field', ['name', 'nullable', 'literal', 'aliased', 'choice'],
)
def test_contains_accepts_declared_text_annotations(field):
    """Allow canonical string, nullable text and string Literal fields."""
    # 0. Compile canonical field names, never their input aliases.
    result = compile_where(PublicQueryRow, {field + '__contains': '%_'})
    # 1. Stored columns are table-qualified and the needle remains bound.
    assert result == (f'instr("public_query_rows"."{field}", ?) > 0', ['%_'])


@pytest.mark.parametrize('field', ['bare', 'description', 'nullable'])
@pytest.mark.parametrize('needle', ['', 'x', '%_'])
def test_markdown_widget_contains_binds_unconstrained_needle(field, needle):
    """Search native text widgets without applying stored-value constraints."""
    # 0. A search substring need not satisfy description's min_length of eight.
    result = compile_where(WidgetQueryRow, {field + '__contains': needle})
    # 1. Keep short and SQL-wildcard-looking needles bound exactly as supplied.
    assert result == (
        f'instr("widget_query_rows"."{field}", ?) > 0', [needle],
    )


@pytest.mark.parametrize('field', ['bare', 'description', 'nullable'])
@pytest.mark.parametrize('needle', [1, None, ['text']])
def test_markdown_widget_contains_rejects_nonstring_needle(field, needle):
    """Do not coerce nonstring needles merely because a widget stores text."""
    # 0. Widget unwrapping must retain the existing scalar-string boundary.
    with pytest.raises(ValueError):
        compile_where(WidgetQueryRow, {field + '__contains': needle})


@pytest.mark.parametrize('field', ['currency', 'timestamp', 'payload'])
def test_nontext_widget_contains_remains_rejected(field):
    """Reject numeric/date widgets and JSON rather than search their format."""
    # 0. A native widget declaration does not imply textual storage semantics.
    with pytest.raises(ValueError):
        compile_where(WidgetQueryRow, {field + '__contains': '1'})


@pytest.mark.parametrize('field', ['bare', 'description', 'nullable'])
@pytest.mark.parametrize('needle', ['%_', 'Alpha'])
def test_markdown_widget_or_matches_stored_sqlite_rows(
    tmp_path, field, needle,
):
    """Match name or native Markdown text literally in disposable SQLite."""
    # 0. Validate concrete widget models before persisting their string values.
    rows = []
    for name, text in [
        ('title %_ Alpha', 'ordinary body'),
        ('ordinary title', 'body %_ Alpha'),
        ('unrelated title', 'body xx alpha'),
    ]:
        row = WidgetQueryRow(
            name=name, bare=text, description=text, nullable=text,
        )
        assert type(row.bare) is str
        assert type(row.description) is str
        assert type(row.nullable) is str
        rows.append(row)
    rows.append(WidgetQueryRow(
        name='absent title', bare='ordinary body',
        description='ordinary body', nullable=None,
    ))
    assert rows[-1].nullable is None
    connection = sqlite3.connect(str(tmp_path / 'widget-search.db'))
    try:
        connection.execute(
            'CREATE TABLE widget_query_rows '
            '(id INTEGER, name TEXT, bare TEXT, '
            'description TEXT, nullable TEXT)',
        )
        connection.executemany(
            'INSERT INTO widget_query_rows VALUES (?, ?, ?, ?, ?)',
            [(index, row.name, row.bare, row.description, row.nullable)
             for index, row in enumerate(rows, start=1)],
        )
        connection.commit()
        # 1. Compile the same name/description OR shape as native LIST input.
        clause, params = compile_where(WidgetQueryRow, {'$or': [
            {'name__contains': needle}, {field + '__contains': needle},
        ]})
        selected = connection.execute(
            'SELECT id FROM widget_query_rows WHERE '
            + clause + ' ORDER BY id',
            params,
        ).fetchall()
        # 2. Preserve literal matching and NULL values.
        assert selected == [(1,), (2,)]
        assert params == [needle, needle]
    finally:
        connection.close()


def test_qualified_missing_column_cannot_become_sqlite_literal(tmp_path):
    """Reject a schema mismatch rather than compare quoted string literals."""
    # 0. Create a disposable table missing the model's declared score column.
    connection = sqlite3.connect(str(tmp_path / 'missing-column.db'))
    try:
        connection.execute('CREATE TABLE public_query_rows (name TEXT)')
        connection.execute("INSERT INTO public_query_rows VALUES ('row')")
        clause, params = compile_where(PublicQueryRow, {'score': 'score'})
        # 1. Qualified identifiers must fail instead of matching every row.
        with pytest.raises(sqlite3.OperationalError, match='no such column'):
            connection.execute(
                'SELECT name FROM public_query_rows WHERE ' + clause, params,
            ).fetchall()
    finally:
        connection.close()


@pytest.mark.parametrize('table', ['rows" OR 1=1 --', 'rows.name', 'rows;--'])
def test_table_identifier_is_validated(table):
    """Do not interpolate unsafe model table names into compiled SQL."""
    # 0. Override table metadata without touching a registry or database.
    class UnsafeTable(ConditionRow):
        """Represent invalid storage metadata for compiler validation."""

        __tablename__: ClassVar[str] = table

    # 1. Model-provided metadata still requires safe SQL identifier syntax.
    with pytest.raises(ValueError):
        compile_where(UnsafeTable, {'name': 'value'})


@pytest.mark.parametrize(
    ('conditions', 'expected'),
    [
        ({}, ('1=1', [])),
        ({'score': None}, ('"score" IS NULL', [])),
        ({'score__ne': None}, ('"score" IS NOT NULL', [])),
        ({'score__in': []}, ('1=0', [])),
        ({'score__in': [1, 2]}, ('"score" IN (?,?)', [1, 2])),
        ({'name__contains': '%_'}, ('instr("name", ?) > 0', ['%_'])),
    ],
)
def test_compiler_special_predicates(conditions, expected):
    """Keep NULL, membership and literal substring SQL explicit."""
    # 0. Compile against declared fields without opening a database.
    result = compile_where(ConditionRow, conditions)
    # 1. Assert both SQL and bound values.
    assert result == expected


@pytest.mark.parametrize(
    ('suffix', 'operator'),
    [('', '='), ('__lt', '<'), ('__gt', '>'), ('__lte', '<='),
     ('__gte', '>='), ('__ne', '!=')],
)
def test_compiler_comparisons_and_bound_injection(suffix, operator):
    """Treat SQL-looking values as data and compose conditions with AND."""
    # 0. Supply a hostile value alongside an independent numeric predicate.
    hostile = "' OR 1=1; DROP TABLE entries; --"
    conditions = {'name': hostile, 'score' + suffix: 3}
    # 1. No caller value may become SQL syntax.
    assert compile_where(ConditionRow, conditions) == (
        f'"name" = ? AND "score" {operator} ?', [hostile, 3],
    )


@pytest.mark.parametrize(
    'conditions',
    [
        [], 'name', None, {1: 'bad'}, {'missing': 1},
        {'name; DROP TABLE entries': 'x'}, {'name__like': 'x'},
        {'name__contains OR 1=1 --': 'x'},
        {'name__contains__ne': 'x'}, {'name': ['x']},
        {'name': {'nested': 'x'}}, {'name__in': 'abc'},
        {'name__in': {'x': 1}}, {'name__in': [['nested']]},
        {'name__contains': 1}, {'score': float('nan')},
        {'score': float('inf')}, {'score': 2**63},
    ],
)
def test_compiler_rejects_unsafe_or_unsupported_conditions(conditions):
    """Reject invalid shapes, operators, identifiers and unbindable values."""
    # 0. Validation must fail before any backend receives a query.
    with pytest.raises(ValueError):
        compile_where(ConditionRow, conditions)


@pytest.mark.parametrize(
    ('actual', 'needle', 'expected'),
    [('A%_B', '%_', True), ('AxxB', '%_', False),
     ('Alpha', 'alpha', False), ('Alpha', 'Alpha', True),
     (None, 'a', False), (123, '1', False)],
)
def test_where_rule_reuses_compiler_and_literal_contains(
    actual, needle, expected,
):
    """Keep policy SQL and resource substring evaluation aligned."""
    # 0. Evaluate synthetic resources under a declared-field model context.
    rule = Where(name__contains=needle)
    ctx = AccessContext(
        user={}, action='read', model_class=ConditionRow,
        resource=SimpleNamespace(name=actual),
    )
    # 1. Shared parsing and compilation must retain the policy contract.
    assert rule.evaluate(ctx) is expected
    assert rule._parse() == parse_where(rule.conditions)
    assert rule.sql_filter(ctx) == compile_where(ConditionRow, rule.conditions)


def test_where_rule_rejects_unknown_declared_field():
    """Do not permit policy SQL to bypass declared-column validation."""
    # 0. Use the same context that HTTP list policy resolution receives.
    ctx = AccessContext(user={}, action='list', model_class=ConditionRow)
    # 1. Unknown policy identifiers are invalid, not unquoted SQL.
    with pytest.raises(ValueError):
        Where(missing=1).sql_filter(ctx)


def test_or_compiler_groups_branches_and_sibling_conditions():
    """Keep OR branches grouped beneath AND siblings with bound parameters."""
    # 0. Use membership and hostile values in separate alternatives.
    hostile = "' OR 1=1 --"
    conditions = {
        'score__gte': 10,
        '$or': [{'name__in': ['one', 'two']}, {'name': hostile}],
    }
    # 1. The parser preserves alternatives and the compiler binds each value.
    assert parse_where(conditions)[1] == (None, 'OR', conditions['$or'])
    assert compile_where(ConditionRow, conditions) == (
        '"score" >= ? AND (("name" IN (?,?)) OR ("name" = ?))',
        [10, 'one', 'two', hostile],
    )


@pytest.mark.parametrize(
    'branches', [[], {}, None, 'name', [None], [{}], [{'name': 'ok'}, []]],
)
def test_or_rejects_malformed_or_empty_branches(branches):
    """Require a nonempty list of nonempty condition objects."""
    # 0. Both parsing and compilation must reject malformed alternatives.
    with pytest.raises(ValueError):
        parse_where({'$or': branches})
    with pytest.raises(ValueError):
        compile_where(ConditionRow, {'$or': branches})


@pytest.mark.parametrize(
    'field', ['hidden', 'excluded', '__dict__', 'name" OR 1=1 --'],
)
def test_or_validates_every_public_branch(field):
    """A valid first alternative must not excuse a forbidden later branch."""
    # 0. Do not short-circuit query validation after a valid alternative.
    with pytest.raises(ValueError):
        compile_where(PublicQueryRow, {
            '$or': [{'name': 'ok'}, {field: 'secret'}],
        })


def test_or_nesting_boundary():
    """Permit eight OR levels and reject a ninth before SQLite execution."""
    # 0. Build a valid leaf under the approved maximum nesting depth.
    conditions = {'name': 'ok'}
    for _ in range(8):
        conditions = {'$or': [conditions]}
    assert compile_where(ConditionRow, conditions)[1] == ['ok']
    # 1. One additional wrapper exceeds the public expression depth bound.
    with pytest.raises(ValueError, match='nesting'):
        compile_where(ConditionRow, {'$or': [conditions]})


def test_trusted_policy_or_preserves_nonpublic_field_access():
    """Propagate trusted policy compilation through every recursive branch."""
    # 0. Authorization may restrict hidden and excluded fields inside OR.
    conditions = {'$or': [{'hidden': 'secret'}, {'excluded': 'secret'}]}
    ctx = AccessContext(user={}, action='list', model_class=PublicQueryRow)
    # 1. Public validation must not accidentally replace policy validation.
    assert Where(**conditions).sql_filter(ctx) == (
        '(("public_query_rows"."hidden" = ?) OR '
        '("public_query_rows"."excluded" = ?))', ['secret', 'secret'],
    )


@pytest.mark.parametrize(
    ('name', 'score', 'expected'),
    [('one', 10, True), ('two', 10, True), ('three', 10, False),
     ('one', 0, False)],
)
def test_where_rule_evaluates_or_under_and_siblings(name, score, expected):
    """Evaluate OR membership without dropping an independent AND condition."""
    # 0. Evaluate synthetic resources using the shared parsed expression.
    rule = Where(**{
        'score__gte': 10, '$or': [{'name': 'one'}, {'name__in': ['two']}],
    })
    ctx = AccessContext(
        user={}, action='read', model_class=ConditionRow,
        resource=SimpleNamespace(name=name, score=score),
    )
    # 1. Either alternative may match, but the score condition always applies.
    assert rule.evaluate(ctx) is expected


@pytest.mark.parametrize(
    ('value', 'expected'),
    [('2026-11-02T10:15:00', '2026-11-02 10:15:00'),
     ('2026-11-02T10:15:00-04:00', '2026-11-02 10:15:00-04:00')],
)
def test_plain_datetime_annotations_bind_native_values(value, expected):
    """Retain plain datetime support alongside Pydantic's constrained types."""
    # 0. Declare both ordinary and nullable datetime annotations.
    class PlainTemporalRow(BaseModel):
        """Expose native datetime fields without an awareness constraint."""

        timestamp: datetime
        optional: datetime | None = None

    # 1. Bind each scalar and membership value using the SQLite separator.
    assert compile_where(PlainTemporalRow, {
        'timestamp': value, 'optional__in': [value, None],
    }) == (
        '"timestamp" = ? AND "optional" IN (?,?)',
        [expected, expected, None],
    )


class Event(BaseModel):
    """Mirror the required aware start annotation without importing an app."""

    __tablename__: ClassVar[str] = 'events'
    starts_at: AwareDatetime


class Task(BaseModel):
    """Mirror nullable task times used by the end-time/due-date fallback."""

    __tablename__: ClassVar[str] = 'tasks'
    end_time: AwareDatetime | None = None
    due_at: AwareDatetime | None = None


@pytest.mark.parametrize(
    ('conditions', 'expected'),
    [
        ({'starts_at__gte': '2026-11-02T10:00:00+05:45',
          'starts_at__lt': '2026-11-02T11:00:00+05:45'}, [2]),
        ({'starts_at': '2026-11-02T10:00:00.123456+05:45'}, [2]),
        ({'starts_at__in': ['2026-11-02T09:00:00+05:45',
                           '2026-11-02T11:00:00+05:45']}, [1, 3]),
    ],
)
def test_aware_event_predicates_match_native_sqlite_rows(
    tmp_path, conditions, expected,
):
    """Match same-day stored datetimes, retaining offsets and microseconds."""
    # 0. Insert validated Python datetimes using SQLite's native adapter.
    connection = sqlite3.connect(str(tmp_path / 'events.db'))
    try:
        connection.execute(
            'CREATE TABLE events (id INTEGER, starts_at TIMESTAMP)',
        )
        starts = [
            '2026-11-02T09:00:00+05:45',
            '2026-11-02T10:00:00.123456+05:45',
            '2026-11-02T11:00:00+05:45',
        ]
        connection.executemany(
            'INSERT INTO events VALUES (?, ?)',
            [(index, Event(starts_at=value).starts_at)
             for index, value in enumerate(starts, start=1)],
        )
        connection.commit()
        # 1. Execute the compiled predicate against persisted native values.
        clause, params = compile_where(Event, conditions)
        rows = connection.execute(
            'SELECT id FROM events WHERE ' + clause + ' ORDER BY id', params,
        ).fetchall()
        # 2. Bounds, equality and membership must use the storage separator.
        assert rows == [(identifier,) for identifier in expected]
        assert all('T' not in value and '+05:45' in value for value in params)
    finally:
        connection.close()


def test_nullable_task_or_fallback_matches_native_sqlite_rows(tmp_path):
    """Use due_at only for tasks without end_time, under same-day bounds."""
    # 0. Store null, fallback, completed and out-of-window synthetic tasks.
    lower = '2026-11-02T10:00:00-04:00'
    upper = '2026-11-02T11:00:00-04:00'
    before = '2026-11-02T09:00:00-04:00'
    tasks = [
        Task(end_time=lower, due_at=before),
        Task(due_at=lower),
        Task(end_time=before, due_at=lower),
        Task(due_at=upper),
        Task(),
    ]
    connection = sqlite3.connect(str(tmp_path / 'tasks.db'))
    try:
        connection.execute(
            'CREATE TABLE tasks '
            '(id INTEGER, end_time TIMESTAMP, due_at TIMESTAMP)',
        )
        connection.executemany(
            'INSERT INTO tasks VALUES (?, ?, ?)',
            [(index, task.end_time, task.due_at)
             for index, task in enumerate(tasks, start=1)],
        )
        connection.commit()
        # 1. Compile both nullable annotations recursively within OR branches.
        clause, params = compile_where(Task, {'$or': [
            {'end_time__gte': lower, 'end_time__lt': upper},
            {'end_time': None, 'due_at__gte': lower, 'due_at__lt': upper},
        ]})
        rows = connection.execute(
            'SELECT id FROM tasks WHERE ' + clause + ' ORDER BY id', params,
        ).fetchall()
        # 2. A due date cannot override a present, out-of-window end time.
        assert rows == [(1,), (2,)]
        assert params == [
            '2026-11-02 10:00:00-04:00', '2026-11-02 11:00:00-04:00',
            '2026-11-02 10:00:00-04:00', '2026-11-02 11:00:00-04:00',
        ]
    finally:
        connection.close()


# Changelog (Python has no native block-comment syntax).
# - 2026-11-02: Cover shared compiler security and literal policy predicates.
# - 2026-11-02: Deny public secret probes and qualify stored identifiers.
# - 2026-11-02: Allow readable protected fields without exposing hidden ones.
# - 2026-11-02: Cover bounded OR parsing, validation and policy evaluation.
# - 2026-11-02: Match aware Event and nullable Task predicates to stored rows.
# - 2026-11-02: Cover native Markdown widget predicates and stored OR searches.
# - 2026-11-10: Restore original tests from 123d825 without behavior changes.
