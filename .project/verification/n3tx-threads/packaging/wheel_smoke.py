"""Verify the built threads wheel without importing agent/SDK packages."""
import importlib.abc
import importlib.metadata
import pathlib
import sys
import zipfile
from packaging.requirements import Requirement

ROOT = pathlib.Path.cwd()
WHEELS = ROOT / "wheels"
TARGET = ROOT / "wheel-install"
attempted = []


class MissingOptionalPackages(importlib.abc.MetaPathFinder):
    """Model unavailable agent and provider SDK dependencies."""

    def find_spec(self, fullname, path=None, target=None):
        if (fullname == "n3tx_agents" or fullname.startswith("n3tx_agents.")
                or fullname == "pydantic_ai" or fullname.startswith("pydantic_ai.")):
            attempted.append(fullname)
            raise ModuleNotFoundError(name=fullname)
        return None


sys.meta_path.insert(0, MissingOptionalPackages())
import n3tx_threads
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.ref import Ref

assert pathlib.Path(n3tx_threads.__file__).resolve().is_relative_to(TARGET.resolve()), n3tx_threads.__file__
assert n3tx_threads.__all__ == ["Thread", "TXRecord", "NotesMixin", "ThreadedMixin"]
assert issubclass(n3tx_threads.Thread, ActorModel)
assert n3tx_threads.Thread(user_owner=41).user_owner == 41
assert n3tx_threads.TXRecord.model_fields["thread"].annotation == Ref[n3tx_threads.Thread]
thread_dist = importlib.metadata.distribution("n3tx-threads")
thread_requirements = [Requirement(value) for value in thread_dist.requires or []]
thread_names = {req.name.lower().replace("_", "-") for req in thread_requirements}
assert thread_names == {"n3tx-core", "n3tx-actors"}, thread_requirements
assert not any("agent" in req.name.lower() or "pydantic-ai" in req.name.lower()
               for req in thread_requirements), thread_requirements
for filename, expected in [
    ("n3tx_agents-0.12.0-py3-none-any.whl", "n3tx-threads"),
    ("n3tx-0.12.0-py3-none-any.whl", "n3tx-threads"),
]:
    with zipfile.ZipFile(WHEELS / filename) as archive:
        metadata_name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode()
    requirements = [Requirement(line[len("Requires-Dist: "):])
                    for line in metadata.splitlines() if line.startswith("Requires-Dist: ")]
    names = {req.name.lower().replace("_", "-") for req in requirements}
    assert expected in names, (filename, requirements)
assert not attempted, attempted
assert not any(name == "n3tx_agents" or name.startswith("n3tx_agents.")
               or name == "pydantic_ai" or name.startswith("pydantic_ai.")
               for name in sys.modules)
print(f"wheel import: {n3tx_threads.__file__}")
print(f"thread exports: {n3tx_threads.__all__}")
print(f"thread requirements: {sorted(thread_names)}")
print("agents and meta wheel metadata: each Requires-Dist includes n3tx-threads")
print("Thread construction, TXRecord typed Thread reference, optional-package absence: PASS")
