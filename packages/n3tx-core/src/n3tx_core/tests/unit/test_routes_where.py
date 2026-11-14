"""Exercise where composition through mixin, SQLite and direct HTTP."""

import json
from inspect import Parameter, signature
from typing import ClassVar
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import Field, PrivateAttr, computed_field

from n3tx_core.api.routes_fastapi import make_get_all_instances
from n3tx_core.authorize import Where
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage

pytestmark = pytest.mark.unit


@pytest.fixture
def where_rows(tmp_path):
    """Create disposable rows with policy, case and wildcard decoys."""
    # 0. Keep the model and its storage local to this fixture.
    class WhereEntry(ProtoModel):
        """Represent searchable rows under a trusted visibility policy."""

        __tablename__: ClassVar[str] = 'where_entries'
        __storable__: ClassVar[bool] = True
        __access__: ClassVar[dict] = {
            'list': Where(visible=True, excluded='secret'),
            'read': Where(visible=True, excluded='secret'),
        }
        __hidden_fields__: ClassVar[set] = {'hidden'}
        __protected_fields__: ClassVar[set] = {
            'protected', 'hidden', 'excluded',
        }
        name: str = ''
        score: int | None = None
        visible: bool = True
        excluded: str = Field(default='secret', exclude=True)
        conditional: str = Field(default='secret', exclude_if=lambda v: True)
        hidden: str = 'secret'
        protected: str = 'secret'
        aliased: str = Field(default='text', alias='external_name')
        payload: list[str] = Field(default_factory=list)
        _private: str = PrivateAttr(default='secret')

        @computed_field
        @property
        def computed(self) -> str:
            """Expose a derived value that cannot be a query column."""
            return self.name

        def describe_secret(self) -> str:
            """Provide a method that public queries must not resolve."""
            return self.excluded

    backend = SQLiteStorage(database=str(tmp_path / 'where.db'))
    WhereEntry.set_storage(backend)
    backend.create_table(WhereEntry)
    for name, score, visible in (
        ('A%_B', 30, True), ('A%_B', 10, True),
        ('A%_B', 20, True), ('a%_b', 40, True),
        ('AxxB', 50, True), ('A%_B', 0, False), ('none', None, True),
    ):
        WhereEntry.create(WhereEntry(
            name=name, score=score, visible=visible, protected=f'p{score}',
        ))
    app = FastAPI()
    handler = make_get_all_instances(WhereEntry)
    app.get('/where_entries')(handler)
    app.get('/WhereEntry/_')(handler)
    # 1. Release all disposable connections even after assertion failures.
    try:
        with TestClient(app) as client:
            yield client, WhereEntry
    finally:
        while not backend._pool.empty():
            backend._pool.get_nowait().close()


def test_mixin_intersects_trusted_sql_and_preserves_backend_api(where_rows):
    """Compile before delegating without adding a storage where keyword."""
    # 0. Capture every existing storage option and a trusted OR expression.
    _, model = where_rows
    backend = Mock()
    model.set_storage(backend)
    trusted = ('visible = ? OR score = ?', [True, 99])
    populate = object()
    # 1. Exercise the public model boundary.
    result = model.list(
        sql_filter=trusted, where={'score__gte': 10}, ids=[1, 2],
        limit=2, offset=1, populate=populate, order_desc='score',
    )
    # 2. Parentheses and parameter order preserve the trusted restriction.
    assert result is backend.list.return_value
    backend.list.assert_called_once_with(
        model,
        sql_filter=('(visible = ? OR score = ?) AND '
                    '("where_entries"."score" >= ?)',
                    [True, 99, 10]),
        ids=[1, 2], limit=2, offset=1, populate=populate, order_desc='score',
    )
    assert trusted[1] == [True, 99]
    assert signature(model.list).parameters['where'].kind is (
        Parameter.KEYWORD_ONLY
    )


def test_sqlite_where_null_membership_ids_and_injection(where_rows):
    """Run compiled predicates against real rows, not SQL mocks."""
    # 0. Read IDs from persisted synthetic rows.
    _, model = where_rows
    rows = model.list()
    # 1. Combine ID selection with NULL, membership and bound hostile values.
    assert len(model.list(where={'score': None})) == 1
    assert len(model.list(where={'score__ne': None})) == 6
    assert model.list(where={'score__in': []}) == []
    selected = model.list(
        where={'score__in': [10, 30]},
        ids=[next(row.id for row in rows if row.score == 30)],
    )
    assert [row.score for row in selected] == [30]
    assert model.list(where={'name': "' OR 1=1 --"}) == []
    assert len(model.list()) == 7


@pytest.mark.parametrize('options', [{}, {'where': None}])
def test_mixin_omitted_where_preserves_sql_filter(where_rows, options):
    """Keep historical backend arguments unchanged without a where dict."""
    # 0. Attach a capturing backend without touching the disposable database.
    _, model = where_rows
    backend = Mock()
    model.set_storage(backend)
    trusted = ('visible = ?', [True])
    # 1. Omission and explicit Python None retain old backend delegation.
    model.list(sql_filter=trusted, **options)
    # 2. No new storage keyword or replacement predicate is introduced.
    backend.list.assert_called_once_with(
        model, sql_filter=trusted, limit=None, offset=None,
        populate=None, ids=None,
    )
    assert backend.list.call_args.kwargs['sql_filter'] is trusted


@pytest.mark.parametrize('path', ['/where_entries', '/WhereEntry/_'])
def test_direct_where_policy_order_and_pages(where_rows, path):
    """Filter with AND before ordering, counts and page selection."""
    # 0. Require literal symbols, exact case and an independent score bound.
    client, _ = where_rows
    params = {
        'where': json.dumps({'name__contains': 'A%_', 'score__gte': 10}),
        'order_desc': 'score', 'limit': 2,
    }
    # 1. Traverse the actual generated list endpoint twice.
    first = client.get(path, params=params)
    last = client.get(path, params={**params, 'offset': 2})
    # 2. Neither denied rows nor wildcard/case decoys affect pages or totals.
    assert first.status_code == last.status_code == 200
    assert [row['score'] for row in first.json()['data']] == [30, 20]
    assert [row['score'] for row in last.json()['data']] == [10]
    assert first.json()['meta'] == {
        'total': 3, 'limit': 2, 'offset': 0, 'has_more': True,
    }
    assert last.json()['meta'] == {
        'total': 3, 'limit': 2, 'offset': 2, 'has_more': False,
    }
    denied = client.get(path, params={'where': '{"visible": false}'})
    assert denied.status_code == 200
    assert denied.json() == []
    hostile = client.get(path, params={
        'where': json.dumps({'name': "' OR 1=1 --"}),
    })
    assert hostile.status_code == 200
    assert hostile.json() == []


@pytest.mark.parametrize(
    'where',
    ['{', 'null', '[]', '"name"', '{"missing": 1}',
     '{"name__like": "x"}', '{"name__in": "abc"}',
     '{"name": ["x"]}', '{"name__contains": 1}',
     '{"score__contains": "1"}', '{"payload__contains": "x"}',
     '{"name__contains OR 1=1 --": "x"}',
     '{"name; DROP TABLE where_entries": "x"}'],
)
def test_direct_invalid_where_is_422(where_rows, where):
    """Reject malformed JSON and invalid compiler inputs without writes."""
    # 0. Exercise the HTTP decoder and downstream compiler.
    client, model = where_rows
    response = client.get('/where_entries', params={'where': where})
    # 1. Client errors must remain structured and non-destructive.
    assert response.status_code == 422
    assert response.json()['detail']
    assert len(model.list()) == 7


def test_direct_omitted_where_retains_legacy_override(where_rows, monkeypatch):
    """Avoid injecting an absent where keyword into older list overrides."""
    # 0. Retain the original override signature with no new keywords.
    client, model = where_rows
    calls = []

    def legacy_list(cls, sql_filter=None, limit=None, offset=None,
                    populate=None, ids=None):
        """Record historical delegation arguments."""
        calls.append((cls, sql_filter, limit, offset))
        return []

    monkeypatch.setattr(model, 'list', classmethod(legacy_list))
    # 1. Omitted filters must retain policy and pagination delegation.
    response = client.get('/where_entries?limit=2&offset=1')
    assert response.status_code == 200
    assert calls == [(
        model,
        ('"where_entries"."visible" = ? AND '
         '"where_entries"."excluded" = ?', [True, 'secret']),
        2, 1,
    )]


@pytest.mark.parametrize('mode', ['where', 'order_asc', 'order_desc'])
@pytest.mark.parametrize(
    'field',
    ['excluded', 'conditional', 'hidden', '_private',
     '__dict__', 'name__class__', 'describe_secret', 'computed',
     'external_name', 'name" OR 1=1 --'],
)
def test_direct_public_queries_cannot_probe_secrets(where_rows, mode, field):
    """Reject secret and nonfield probes for both filtering and sorting."""
    # 0. An incoming public flag must never enable trusted compilation.
    client, model = where_rows
    value = json.dumps({field: 'secret'}) if mode == 'where' else field
    response = client.get('/where_entries', params={
        mode: value, 'public': 'false',
    })
    # 1. Policy may use excluded columns, but public queries may not.
    assert response.status_code == 422
    assert response.json()['detail']
    assert len(model.list()) == 7


def test_direct_trusted_policy_filters_excluded_storage_field(where_rows):
    """Prove excluded-column policy restrictions affect the actual row set."""
    # 0. Keep a visible matching row but make its excluded value policy-denied.
    client, model = where_rows
    row = model.list(where={'score': 30})[0]
    model.update(row.id, {'excluded': 'denied'})
    assert model.get(row.id).excluded == 'denied'
    # 1. Public filtering must intersect the trusted excluded-field policy.
    response = client.get('/where_entries', params={
        'where': '{"score": 30}', 'limit': 2,
    })
    # 2. Neither result rows nor counts may disclose the denied row.
    assert response.status_code == 200
    assert response.json()['data'] == []
    assert response.json()['meta']['total'] == 0


@pytest.mark.parametrize(
    ('ordering', 'expected'),
    [('order_asc', ['p10', 'p20']), ('order_desc', ['p20', 'p10'])],
)
def test_sqlite_queries_readable_protected_field(
    where_rows, ordering, expected,
):
    """Filter and order write-protected fields through native Python storage."""
    # 0. Include a policy-denied row in caller-supplied protected values.
    _, model = where_rows
    conditions = {'protected__in': ['p0', 'p10', 'p20']}
    # 1. Apply the trusted restriction before sorting the intersection.
    page = model.list(
        where=conditions, sql_filter=('visible = ?', [True]), limit=2,
        **{ordering: 'protected'},
    )
    # 2. Readability permits querying, not bypassing the trusted restriction.
    assert [row.protected for row in page['data']] == expected
    assert page['meta']['total'] == 2


@pytest.mark.parametrize('path', ['/where_entries', '/WhereEntry/_'])
@pytest.mark.parametrize(
    ('ordering', 'expected'),
    [('order_asc', ['p10', 'p20']), ('order_desc', ['p20', 'p10'])],
)
def test_direct_queries_readable_protected_field(
    where_rows, path, ordering, expected,
):
    """Allow public protected-field queries while preserving list policy."""
    # 0. Select values shared by two allowed rows and a denied decoy.
    client, _ = where_rows
    # 1. Exercise protected-field filtering and ordering together over HTTP.
    response = client.get(path, params={
        'where': json.dumps({'protected__in': ['p0', 'p10', 'p20']}),
        ordering: 'protected', 'limit': 2,
    })
    # 2. Readable protected values are returned only from authorized rows.
    assert response.status_code == 200
    assert [row['protected'] for row in response.json()['data']] == expected
    assert response.json()['meta']['total'] == 2


@pytest.mark.parametrize('path', ['/where_entries', '/WhereEntry/_'])
def test_direct_or_cannot_escape_policy_or_sibling_conditions(
    where_rows, path,
):
    """Apply trusted policy outside the complete OR expression."""
    # 0. The second branch targets a denied row, and the third is hostile data.
    client, model = where_rows
    conditions = {
        '$and': [
            {'score__lte': 20},
            {'name__lt': 'a'},
            {'$or': [{'score__in': [10, 20, 30]}, {'visible': False}]},
        ],
        '$or': [{'score__in': [10, 20, 30]}, {'score__in': [10]},
                {'visible': False},
                {'name': "' OR 1=1 --"}],
    }
    # 1. Exercise SQLite through both Python and the direct HTTP boundary.
    page = model.list(
        where=conditions, sql_filter=('visible = ?', [True]),
        order_desc='score', limit=1,
    )
    response = client.get(path, params={
        'where': json.dumps(conditions), 'order_desc': 'score', 'limit': 1,
    })
    last = client.get(path, params={
        'where': json.dumps(conditions), 'order_desc': 'score',
        'limit': 1, 'offset': 1,
    })
    # 2. Neither OR nor membership can widen policy or bypass sibling ANDs.
    assert [row.score for row in page['data']] == [20]
    assert page['meta']['total'] == 2
    assert response.status_code == 200
    assert [row['score'] for row in response.json()['data']] == [20]
    assert response.json()['meta']['total'] == 2
    assert last.status_code == 200
    assert [row['score'] for row in last.json()['data']] == [10]
    assert last.json()['meta'] == {
        'total': 2, 'limit': 1, 'offset': 1, 'has_more': False,
    }


@pytest.mark.parametrize(
    'conditions',
    [{'$or': []}, {'$or': [{}]}, {'$or': {'name': 'x'}},
     {'$or': [{'name': 'ok'}, {'hidden': 'secret'}]},
     {'$or': [{'name': 'ok'}, {'excluded': 'secret'}]},
     {'$or': [{'name': 'ok'}, {'name__like': 'x'}]},
     {'$or': [{'name': 'ok'}, {'name" OR 1=1 --': 'x'}]},
     {'$and': []}, {'$and': [{}]}, {'$and': {'name': 'x'}},
     {'$and': [{'name': 'ok'}, {'hidden': 'secret'}]},
     {'$and': [{'name': 'ok'}, {'excluded': 'secret'}]},
     {'$and': [{'name': 'ok'}, {'score__like': '1'}]}],
)
def test_direct_invalid_or_is_422(where_rows, conditions):
    """Reject malformed alternatives and unsafe fields in every branch."""
    # 0. Send the expression through the actual JSON query decoder.
    client, _ = where_rows
    response = client.get('/where_entries', params={
        'where': json.dumps(conditions),
    })
    # 1. Invalid alternatives must not become partial or unrestricted reads.
    assert response.status_code == 422
    assert response.json()['detail']


def test_direct_deep_or_is_422(where_rows):
    """Bound recursive public expressions before executing a list query."""
    # 0. Construct nine nested alternatives around an otherwise valid leaf.
    client, _ = where_rows
    conditions = {'name': 'ok'}
    for index in range(9):
        conditions = {'$and' if index % 2 else '$or': [conditions]}
    # 1. Exercise depth validation through direct HTTP.
    response = client.get('/where_entries', params={
        'where': json.dumps(conditions),
    })
    assert response.status_code == 422


# Changelog
# - 2026-11-13: Intersect fixed AND and search OR before native policy pages;
#   reject invalid AND inputs and mixed logical depth overflow.
# - 2026-11-02: Cover native where delegation, SQLite and direct HTTP.
# - 2026-11-02: Reject public secret probes and preserve trusted policy access.
# - 2026-11-02: Query readable protected fields without bypassing list policy.
# - 2026-11-02: Protect OR policy intersection and invalid HTTP expressions.
# - 2026-11-10: Restore original tests from 123d825 without behavior changes.
