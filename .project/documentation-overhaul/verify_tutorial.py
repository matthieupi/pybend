"""Extract and check the documented app; no providers or remote dereferences.

Run with /workspace/.venv-agents/bin/python from any working directory.
Only disposable files under the owned documentation artifact directory are created.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
for package in ('n3tx-core', 'n3tx-ui'):
    sys.path.insert(0, str(ROOT / 'packages' / package / 'src'))
os.environ['N3TX_DEBUG'] = 'false'
os.environ['N3TX_API_URL'] = 'http://localhost:5000'
os.environ['N3TX_JWT_SECRET'] = 'isolated-documentation-test-secret-not-for-deployment'
os.environ['N3TX_REMOTES'] = '{}'


def main():
    source = (ROOT / 'docs/GETTING_STARTED.md').read_text()
    match = re.search(r'<!-- tutorial: main.py -->\s*```python\n(.*?)\n```', source, re.S)
    assert match is not None
    code = match[1]
    from fastapi.testclient import TestClient
    checks = []
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix='tutorial-', dir=Path(__file__).parent) as directory:
        os.chdir(directory)
        try:
            module_path = Path(directory) / 'main.py'
            module_path.write_text(code)
            (Path(directory) / 'static').mkdir()
            spec = importlib.util.spec_from_file_location('tutorial_main', module_path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            with TestClient(module.app) as client:
                def request(method, path, status=200, token=None, **kwargs):
                    headers = {'x-access-token': token} if token else {}
                    response = client.request(method, path, headers=headers, **kwargs)
                    assert response.status_code == status, (method, path, status, response.status_code, response.text)
                    checks.append(f'{method} {path}: {status}')
                    return response

                schema = request('GET', '/Issue').json()
                assert schema['methods']['resolve']['requires_instance'] is True
                assert 'user' not in schema['methods']['resolve']['parameters']
                assert schema['properties']['related']['items']['x-ref'] == 'Label'
                assert schema['ui']['renderer']['list'] == 'ntx-list'
                assert 'name' in schema['required']
                assert 'title' not in schema['properties']
                request('GET', '/openapi.json')
                alice = request('POST', '/users/register', json={
                    'name': 'Alice', 'email': 'alice@example.com', 'password': 'tutorial-only-password'
                }).json()
                assert alice['user']['role'] == 'user'
                assert 'password_hash' not in alice['user']
                request('POST', '/users/register', status=409, json={
                    'name': 'Alice', 'email': 'alice@example.com', 'password': 'tutorial-only-password'
                })
                token = request('POST', '/users/login', json={
                    'email': 'alice@example.com', 'password': 'tutorial-only-password'
                }).json()['token']
                request('POST', '/users/login', status=401, json={'email': 'alice@example.com', 'password': 'wrong'})
                request('GET', '/Issue', status=401, token='invalid')
                request('POST', '/issues', status=403, json={'name': 'anonymous'})
                label = request('POST', '/labels', status=201, token=token, json={'name': 'bug'}).json()
                ref = 'https://example.invalid/Label/42'
                issue = request('POST', '/issues', status=201, token=token, json={
                    'name': 'Fix keyboard navigation', 'labels': [label['id']],
                    'related': [ref], 'user_owner': 999,
                }).json()
                ident = issue['id']
                assert issue['user_owner'] == alice['user']['id']
                assert issue['labels'][0]['id'] == label['id']
                read_issue = request('GET', f'/Issue/{ident}', token=token).json()
                assert read_issue['labels'][0]['$id'].endswith('/Label/1'), read_issue
                assert issue['related'] == [ref]
                assert request('GET', '/issues').json() == []
                request('GET', f'/Issue/{ident}', status=403)
                page = request('GET', '/issues?limit=20&offset=0', token=token).json()
                assert page['meta']['total'] == 1 and len(page['data']) == 1
                changed = request('PUT', f'/issues/{ident}', token=token, json={'name': 'Fix keyboard focus order', 'user_owner': 999}).json()
                assert changed['name'] == 'Fix keyboard focus order'
                assert changed['labels'] == issue['labels']
                assert changed['user_owner'] == alice['user']['id']
                request('PUT', f'/issues/{ident}', status=422, token=token, json={'name': ''})
                request('POST', '/issues', status=422, token=token, json={'name': '<b>bad</b>'})
                request('PUT', f'/issues/{ident}', status=422, token=token, json={'status': 'closed'})
                request('PUT', f'/issues/{ident}', status=422, token=token, json={'related': [1]})
                bob = request('POST', '/users/register', json={'name': 'Bob', 'email': 'bob@example.com', 'password': 'tutorial-only-password'}).json()['token']
                assert request('GET', '/issues', token=bob).json() == []
                for method, path, payload in [
                    ('GET', f'/Issue/{ident}', None),
                    ('PUT', f'/Issue/{ident}', {'name': 'stolen'}),
                    ('POST', f'/Issue/{ident}/resolve', {'resolution': 'stolen'}),
                    ('DELETE', f'/Issue/{ident}', None),
                ]:
                    request(method, path, status=403, token=bob, **({'json': payload} if payload else {}))
                request('POST', f'/issues/{ident}/resolve', status=400, token=token, json={})
                request('POST', f'/issues/{ident}/resolve', status=400, token=token, json={'resolution': ' '})
                resolved = request('POST', f'/issues/{ident}/resolve', token=token, json={'resolution': 'Fixed', 'user': {'user_id': 999}}).json()
                assert resolved['resolved_by'] == alice['user']['id']
                assert resolved['issue']['status'] == 'closed'
                request('POST', f'/issues/{ident}/resolve', status=409, token=token, json={'resolution': 'Again'})
                with sqlite3.connect('issues.db') as connection:
                    row = connection.execute('SELECT name,status,labels,related FROM issues WHERE id=?', (ident,)).fetchone()
                assert row == ('Fix keyboard focus order', 'closed', '[1]', json.dumps([ref]))
                for path, marker in [('/Issue/@', 'ntx-list'), (f'/Issue/{ident}/@', 'ntx-item')]:
                    assert marker in request('GET', path).text
                for path in ['/login.html', '/core/NTT.js', '/components/ntx-list.js', '/components/ntx-item.js']:
                    request('GET', path)
                cleared = request('PUT', f'/issues/{ident}', token=token, json={'labels': []}).json()
                assert cleared['labels'] == []
                request('DELETE', f'/issues/{ident}', token=token)
                request('GET', f'/Issue/{ident}', status=404, token=token)
                request('GET', '/Label/1')
            print(json.dumps({'result': 'PASS', 'http_checks': len(checks), 'checks': checks,
                              'additional': ['schema contract', 'caller forgery ignored', 'SQLite persisted values',
                                             'relationship replacement leaves child', 'HTML shell and asset delivery'],
                              'not_checked': ['browser rendering', 'process restart', 'concurrent writes', 'actor transport']}, indent=2))
        finally:
            os.chdir(old_cwd)


if __name__ == '__main__':
    main()
