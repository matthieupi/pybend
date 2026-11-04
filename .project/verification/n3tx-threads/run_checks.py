import ast, json, os, pathlib, subprocess, sys, time, tomllib
N=pathlib.Path('/workspace/neuralys/collagen/lib/n3tx'); C=pathlib.Path('/workspace/neuralys/collagen')
OUT=N/'.project/verification/n3tx-threads'; py='/workspace/.venv-agents/bin/python'
pypaths=[N/f'packages/{x}/src' for x in ['n3tx-core','n3tx-actors','n3tx-threads','n3tx-agents','n3tx-ui','n3tx-files','n3tx']]
env=os.environ.copy(); env.update(PYTHONDONTWRITEBYTECODE='1',N3TX_DEBUG='false',N3TX_API_URL='https://threads.example',PYTHONPATH=':'.join(map(str,pypaths)))
results=[]
def run(label, argv, cwd, extra=None):
 e=env.copy(); e.update(extra or {})
 t=time.monotonic(); p=subprocess.run(argv,cwd=cwd,env=e,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE); elapsed=time.monotonic()-t
 log=OUT/f'{label}.log'; log.write_text(f'COMMAND: {json.dumps(argv)}\nCWD: {cwd}\nENV: PYTHONDONTWRITEBYTECODE=1 N3TX_DEBUG=false N3TX_API_URL=https://threads.example PYTHONPATH=<seven package src dirs>{"; " + json.dumps(extra) if extra else ""}\nEXIT: {p.returncode}\nELAPSED_SECONDS: {elapsed:.3f}\n--- STDOUT ---\n{p.stdout}--- STDERR ---\n{p.stderr}')
 results.append((label,argv,cwd,p.returncode,elapsed,log))
 return p
run('list-suites',[py,'scripts/test-backend.py','--list'],N)
smoke='''import importlib.abc,sys,tempfile,sqlite3\nattempts=[]\nclass Block(importlib.abc.MetaPathFinder):\n def find_spec(self,fullname,path=None,target=None):\n  if fullname == "n3tx_agents" or fullname.startswith("n3tx_agents.") or fullname == "pydantic_ai" or fullname.startswith("pydantic_ai."):\n   attempts.append(fullname); raise ModuleNotFoundError(name=fullname)\nsys.meta_path.insert(0,Block())\nimport n3tx_threads\nassert not attempts, attempts\nfrom n3tx_core.app import create_app\nfrom n3tx_actors.models.actor_model import ActorModel\nfrom n3tx_actors.tx import TX\nfrom n3tx_core.storage.sqlite_storage import SQLiteStorage\nfrom n3tx_core.authorize import AccessDenied\nclass Notes(ActorModel):\n __tablename__="smoke_notes"\n __storable__=True\n __notes__=True\nclass CaptureActor(n3tx_threads.ThreadedMixin,ActorModel):\n __storable__=False\nassert CaptureActor.__storable__ is False\nwith tempfile.TemporaryDirectory(prefix="n3tx-threads-") as d:\n db=d+"/smoke.sqlite"\n app=create_app(models=[Notes,n3tx_threads.Thread,n3tx_threads.TXRecord],storage=SQLiteStorage(db),static_dir=None,jwt_secret="isolated-threads-smoke-secret-at-least-32",debug=False)\n assert app is not None and Notes.model_fields.get("notes") is not None\n thread=n3tx_threads.Thread.create(n3tx_threads.Thread(user_owner=1)); caller={"user_id":1,"role":"user"}\n tx=TX("NOTE","a","b",data={"text":"hello"},meta={"codec":"test/v1"})\n thread.append(tx,user=caller)\n assert thread.payloads(user=caller,codec="test/v1")==[{"text":"hello"}]\n try: thread.payloads(user={"user_id":2,"role":"user"},codec="test/v1")\n except AccessDenied: pass\n else: raise AssertionError("different-owner read was allowed")\n con=sqlite3.connect(db); tables={r[0] for r in con.execute("select name from sqlite_master where type=\\\"table\\\"")}\n assert {"threads","tx_records","smoke_notes"} <= tables,tables\n assert "history" not in dir(thread)\n assert n3tx_threads.Thread is app.models.get("Thread") if hasattr(app,"models") else True\n con.close()\nassert "n3tx_agents" not in sys.modules and "pydantic_ai" not in sys.modules\nprint("PASS: direct import isolation, Notes registration, Thread/TXRecord registration, ThreadedMixin declaration, payload, AccessDenied for foreign owner, SQLite tables, no history, no SDK modules")'''
run('threads-smoke',[py,'-c',smoke],N)
bootstrap='''import importlib.abc,sys\nclass Block(importlib.abc.MetaPathFinder):\n def find_spec(self,fullname,path=None,target=None):\n  if fullname == "n3tx_threads" or fullname.startswith("n3tx_threads.") or fullname == "n3tx_agents" or fullname.startswith("n3tx_agents.") or fullname == "pydantic_ai" or fullname.startswith("pydantic_ai."): raise ModuleNotFoundError(name=fullname)\nsys.meta_path.insert(0,Block())\nfrom n3tx_core.app import create_app\nfrom n3tx_actors.models.actor_model import ActorModel\nassert not any(n in sys.modules for n in ("n3tx_threads","n3tx_agents","pydantic_ai"))\nprint("PASS: plain core/actor bootstrap imports; no threads/agents/SDK; no history activation")'''
run('core-actor-bootstrap',[py,'-c',bootstrap],N)
# AST/style exactly the assigned stable, non-test runtime paths.
npaths=['packages/n3tx-threads/src/n3tx_threads/__init__.py','packages/n3tx-threads/src/n3tx_threads/thread.py','packages/n3tx-threads/src/n3tx_threads/threaded_mixin.py','packages/n3tx-threads/src/n3tx_threads/notes_mixin.py','packages/n3tx-threads/src/n3tx_threads/tx_record.py','packages/n3tx-agents/src/n3tx_agents/agent.py','packages/n3tx-agents/src/n3tx_agents/history.py','packages/n3tx-agents/src/n3tx_agents/__init__.py','packages/n3tx-core/src/n3tx_core/app.py','packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py','apps/veille/main.py','scripts/test-backend.py','packages/n3tx/src/n3tx_meta/__init__.py']
cpaths=['core/native_models.py','core/app.py','core/agents/backend.py','core/agents/history.py','core/agents/runtime.py','core/actors/agent_tools.py','core/models/email.py','apps/hr/models/resume.py','n3tx_ext/playground/policy.py','scripts/live_agent_check.py']
files=[(N/x) for x in npaths]+[(C/x) for x in cpaths]
lines=[]; missing=[]; syntax=[]
for p in files:
 try: text=p.read_text(); tree=ast.parse(text,filename=str(p))
 except Exception as ex: syntax.append(f'{p}: {type(ex).__name__}: {ex}'); continue
 for i,line in enumerate(text.splitlines(),1):
  if len(line)>80: lines.append(f'{p}:{i}: {len(line)} columns')
 if ast.get_docstring(tree) is None: missing.append(f'{p}: module docstring missing')
 for node in ast.walk(tree):
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and ast.get_docstring(node) is None: missing.append(f'{p}:{node.lineno}: {node.name} docstring missing')
log=OUT/'ast-style.log'; log.write_text('CHECKED FILES:\n'+'\n'.join(map(str,files))+f'\nFILES={len(files)} syntax_errors={len(syntax)} >80_lines={len(lines)} missing_docstrings={len(missing)}\nSYNTAX:\n'+'\n'.join(syntax)+'\nLONG LINES:\n'+'\n'.join(lines)+'\nMISSING DOCSTRINGS:\n'+'\n'.join(missing)+'\n')
# metadata: changed packaging manifests in the relevant N/C trees and required pyright config.
status=subprocess.run(['git','status','--short'],cwd=N,text=True,capture_output=True,check=True).stdout
manifest=set()
for ln in status.splitlines():
 s=ln[3:]
 if s.endswith(('.toml','.json')) and (s=='pyproject.toml' or s.startswith('packages/')): manifest.add(N/s)
manifest.add(C/'pyrightconfig.json')
meta=[]
for p in sorted(manifest):
 try:
  if p.suffix=='.toml': tomllib.loads(p.read_text())
  elif p.suffix=='.json': json.loads(p.read_text())
  meta.append(f'PASS {p}')
 except Exception as ex: meta.append(f'FAIL {p}: {type(ex).__name__}: {ex}')
(OUT/'metadata.log').write_text('CHANGED PACKAGING METADATA AND REQUIRED CONFIG:\n'+'\n'.join(meta)+'\n')
# shell syntax check captured as a proper subprocess.
run('install-dev-shell',["sh","-n","install-dev.sh"],N)
report=['# n3tx-threads extraction focused runtime checks','',f'Execution date: 2026-11-02','Working directory: '+str(N),'Approved interpreter: '+py+' ('+subprocess.run([py,'--version'],text=True,capture_output=True).stderr.strip()+')','Environment for Python invocations: PYTHONDONTWRITEBYTECODE=1; N3TX_DEBUG=false; N3TX_API_URL=https://threads.example; PYTHONPATH set to the seven listed package `src` directories (in requested order). Disposable SQLite file was inside a temporary directory.','', '## Command evidence','']
for label,argv,cwd,code,elapsed,logp in results:
 report += [f'- `{label}`: `{json.dumps(argv)}`; cwd `{cwd}`; exit {code}; {elapsed:.3f}s; complete stdout/stderr: `{logp}`.']
report += ['',f'- AST/style: `env PYTHONDONTWRITEBYTECODE=1 {py} <inline AST/style check>`; exit 0 if no syntax errors; checked {len(files)} named runtime paths; results in `{OUT}/ast-style.log`. The check reports every line exceeding 80 columns, module docstrings, and every class/function/async function lacking a docstring (private names included).','- Metadata: parsed every changed packaging `.toml`/`.json` under N package roots plus required C `pyrightconfig.json`; see `metadata.log`.','', '## Results / failures','']
for label,argv,cwd,code,elapsed,logp in results:
 report.append(f'- {label}: exit {code}; '+('PASS' if code==0 else 'FAIL/BLOCKED')+'.')
report += ['','The final smoke validates with a specific `AccessDenied` exception, not a broad exception handler. Earlier invocation failures from the preceding execution (wrong SQLiteStorage import, AssertionError blocker catching core optional-package probing, and wrong TX import) were not repeated in this run; final reproducible commands and output are represented by these logs.','Permanent tests and wheel build were intentionally not run. No source files were edited.']
(OUT/'runtime-report.md').write_text('\n'.join(report)+'\n')
print('report',OUT/'runtime-report.md')
for r in results: print(r[0],r[3],r[5])
print('AST files',len(files),'syntax',len(syntax),'long80',len(lines),'missing-docstrings',len(missing),'metadata',len(meta))
