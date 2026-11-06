"""Assert package member and metadata closure in the built wheels."""
from email.parser import Parser
import pathlib
import zipfile

root = pathlib.Path.cwd()
wheels = root / 'wheels'
paths = {
    'agents': wheels / 'n3tx_agents-0.12.0-py3-none-any.whl',
    'threads': wheels / 'n3tx_threads-0.12.0-py3-none-any.whl',
    'meta': wheels / 'n3tx-0.12.0-py3-none-any.whl',
}
archives = {name: zipfile.ZipFile(path) for name, path in paths.items()}
members = {name: set(archive.namelist()) for name, archive in archives.items()}
for name in ('agents', 'threads', 'meta'):
    metadata_path = next(p for p in members[name] if p.endswith('.dist-info/METADATA'))
    metadata = Parser().parsestr(archives[name].read(metadata_path).decode())
    print(f'[{name}] members:')
    for member in sorted(members[name]):
        print(member)
    print(f'[{name}] Name={metadata.get("Name")} Version={metadata.get("Version")}')
    print(f'[{name}] Requires-Dist={metadata.get_all("Requires-Dist", [])}')

stale = {
    'n3tx_agents/thread.py',
    'n3tx_agents/tx_record.py',
    'n3tx_agents/notes_mixin.py',
    'n3tx_agents/threaded_mixin.py',
}
assert not (members['agents'] & stale), sorted(members['agents'] & stale)
canonical = {
    'n3tx_threads/thread.py',
    'n3tx_threads/tx_record.py',
    'n3tx_threads/notes_mixin.py',
    'n3tx_threads/threaded_mixin.py',
}
assert canonical <= members['threads'], sorted(canonical - members['threads'])
assert not any(member.startswith(('n3tx_agents/', 'pydantic_ai/')) for member in members['threads'])
agent_runtime = archives['agents'].read('n3tx_agents/agent.py').decode()
agent_history = archives['agents'].read('n3tx_agents/history.py').decode()
assert 'from n3tx_threads import Thread' in agent_runtime
assert 'from n3tx_threads.threaded_mixin import current_execution' in agent_runtime
assert 'from n3tx_threads import Thread' in agent_history
for name in ('agents', 'meta'):
    metadata_path = next(p for p in members[name] if p.endswith('.dist-info/METADATA'))
    metadata = Parser().parsestr(archives[name].read(metadata_path).decode())
    requirements = metadata.get_all('Requires-Dist', []) or []
    assert any(req.lower().startswith('n3tx-threads') for req in requirements), (name, requirements)
print('PASS: clean extraction wheel member closure, canonical imports, and dependency metadata')
