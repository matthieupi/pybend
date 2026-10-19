"""Extract actual tutorial blocks, serve disposable SQLite, run Chromium smoke."""
import os
import json
import httpx
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

def block(text, name, language):
    return re.search(r'<!-- tutorial: ' + re.escape(name) + r' -->\s*```' + language + r'\n(.*?)```', text, re.S)[1]

def main():
    text = (ROOT / 'docs/GETTING_STARTED.md').read_text()
    with tempfile.TemporaryDirectory(prefix='t02e-', dir=OUT) as directory:
        app = Path(directory)
        (app / 'static').mkdir()
        (app / 'main.py').write_text(block(text, 'main.py', 'python'))
        (app / 'static/index.html').write_text(block(text, 'static/index.html', 'html'))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'N3TX_DEBUG': 'false', 'N3TX_API_URL': origin,
               'N3TX_JWT_SECRET': 'disposable-documentation-smoke-not-production'}
        with (OUT / 't02e-server.log').open('w') as log:
            server = subprocess.Popen(['/workspace/.venv-agents/bin/python', '-m', 'uvicorn',
                                       'main:app', '--host', '127.0.0.1', '--port', str(port)],
                                      cwd=app, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen(origin + '/Issue').close()
                        break
                    except OSError:
                        if server.poll() is not None:
                            raise RuntimeError('server exited; see t02e-server.log')
                        time.sleep(.2)
                verify_http(origin)
                result = subprocess.run(['node', str(OUT / 't02e_browser.mjs'), origin], cwd=ROOT,
                                        text=True, capture_output=True)
                (OUT / 't02e-browser-launch.log').write_text(result.stdout + result.stderr)
                print(result.stdout or result.stderr)
                result.check_returncode()
            finally:
                server.terminate()
                server.wait(timeout=10)

def verify_http(origin):
    checks = []
    with httpx.Client(base_url=origin) as client:
        def check(method, path, expected, **kwargs):
            response = client.request(method, path, **kwargs)
            checks.append({'method': method, 'path': path, 'status': response.status_code,
                           'expected': expected})
            assert response.status_code == expected, response.text
            return response.json()
        schema = check('GET', '/Issue', 200)
        assert 'name' in schema['required'] and 'title' not in schema['properties']
        (OUT / 't02e-issue-schema.json').write_text(json.dumps(schema, indent=2))
        for name in ['Alice', 'Bob']:
            check('POST', '/users/register', 200, json={'name': name,
                  'email': name.lower() + '@example.com', 'password': 'tutorial-only-password'})
        alice = check('POST', '/users/login', 200, json={'email': 'alice@example.com', 'password': 'tutorial-only-password'})
        bob = check('POST', '/users/login', 200, json={'email': 'bob@example.com', 'password': 'tutorial-only-password'})
        a = {'x-access-token': alice['token']}
        b = {'x-access-token': bob['token']}
        check('GET', '/auth/me', 200, headers=a)
        check('POST', '/labels', 422, headers=a, json={'name': '<b>bad</b>'})
        check('POST', '/labels', 201, headers=a, json={'name': 'bug'})
        check('POST', '/issues', 422, headers=a, json={'name': '<b>bad</b>'})
        check('POST', '/issues', 422, headers=a, json={'title': 'Not the heading'})
        issue = check('POST', '/issues', 201, headers=a, json={'name': 'HTTP smoke'})
        path = '/issues/' + str(issue['id'])
        assert check('PUT', path, 200, headers=a, json={'name': 'HTTP edited'})['name'] == 'HTTP edited'
        check('PUT', path, 422, headers=a, json={'name': ''})
        check('POST', path + '/resolve', 200, headers=a, json={'resolution': 'HTTP resolved'})
        saved = check('GET', path, 200, headers=a)
        assert saved['status'] == 'closed' and saved['resolution'] == 'HTTP resolved'
        assert check('GET', '/issues', 200, headers=b) == []
        for method, suffix, data in [('GET', '', None), ('PUT', '', {'name': 'Denied'}),
                                     ('POST', '/resolve', {'resolution': 'Denied'}), ('DELETE', '', None)]:
            check(method, path + suffix, 403, headers=b, json=data)
        check('DELETE', path, 200, headers=a)
    (OUT / 't02e-http-results.json').write_text(json.dumps(checks, indent=2))
    print(f'HTTP checks passed: {len(checks)} (not browser coverage)')

if __name__ == '__main__':
    main()
