"""AgentMixin — model policy over native Matrix and the single SDK loop.

API: ctx/tools/run_config resolve trusted policy; agentic/agentic_stream route
through Matrix AGENTIC; run/run_stream are guarded execution seams requiring a
saved TTX. AGENTIC requires an explicit callee AccessRule and metadata caller.

Boundary: client commands never select providers, prompts, tools or retries.
Trusted CallConfig crosses Matrix in task-local Python state. History policy
is separate from fresh application business guards. No HTTP agent execution
route or universal stock-agent grant is installed."""

import json
import logging

from pydantic_core import to_jsonable_python

from n3tx_core import config
from n3tx_core.authorize import (
    AccessContext, AccessDenied, AccessRule, DefaultResolver,
)
from n3tx_core.models.proto_schema import run_pipeline
from n3tx_core.models.ref import Ref
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.introspection import get_fk_list_fields
from n3tx_actors.tx import TX
from n3tx_threads import TTX

from .agent import Agent, CallConfig, _trusted_call
from .utils import _agent_addr, _build_instance_text, _caller_user


logger = logging.getLogger("n3tx.agents")


def _validate_options(options: dict, *, runtime: bool = False) -> None:
    """Reject unknown options instead of silently creating new history."""
    allowed = {"llm"} if runtime else {
        "prompt", "tools", "user", "constraints", "result_type", "llm", "scope",
    }
    unknown = options.keys() - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise TypeError(f"Unsupported agent call arguments: {names}")


def _authorize_agentic(target, user) -> None:
    """Require explicit callee policy before configuration or history reads."""
    cls = target if isinstance(target, type) else type(target)
    access = getattr(cls, "__access__", {})
    if not isinstance(access, dict) or not isinstance(
        access.get("AGENTIC"), AccessRule,
    ):
        raise PermissionError("AGENTIC is not enabled for this actor")
    # 0. Missing callers retain native trusted-internal semantics only.
    caller = _caller_user(user)
    if caller is not None:
        try:
            DefaultResolver().authorize(AccessContext(
                user=caller, action="AGENTIC", model_class=cls,
                resource=None if isinstance(target, type) else target,
            ))
        except AccessDenied as error:
            raise PermissionError("Access denied for AGENTIC") from error


def _record_return(target, owner: TTX, result: dict) -> None:
    """Attach the guarded result as JSON evidence without runtime metadata."""
    cls = target if isinstance(target, type) else type(target)
    # 0. SDK messages already have one codec journal; do not duplicate them.
    payload = {key: value for key, value in result.items() if key != "messages"}
    owner.ATTACH(TTX.from_tx(TX(
        "RETURN", _agent_addr(target, cls), f"ttx/{owner.id}",
        data=to_jsonable_python(payload),
    )))


class AgentMixin:
    """Model policy, Matrix admission and guarded native execution.

    API: ctx/tools/run_config resolve policy; agentic routes through Matrix;
    AGENTIC authorizes and calls run, retaining application run overrides.
    Streaming mirrors the same ownership, caller and trusted-config boundary.
    Compose through __agent__ before defining models; register TTX storage.
    Applications must explicitly declare AGENTIC and keep fresh domain guards
    in run/run_stream. History ownership never grants business access."""

    @fullmethod
    def ctx(target) -> str:
        """Build schema and instance context under model prompt policy."""
        # 0. Resolve the model's native schema projection.
        cls = target if isinstance(target, type) else type(target)
        flag = getattr(cls, "__agent__", False)
        conf = flag if isinstance(flag, dict) else {}
        cleaned = run_pipeline(cls, pipeline="llm")
        table = getattr(cls, "__tablename__", cls.__name__)
        context = (
            f"You operate on {cls.__name__} entities (table: {table}).\n\n"
            f"Schema:\n{json.dumps(cleaned, indent=2)}"
        )
        # 1. Add trusted prompt and instance data without changing storage.
        if conf.get("prompt"):
            context = conf["prompt"] + "\n\n" + context
        if not isinstance(target, type):
            context += _build_instance_text(target)
        return context

    @fullmethod
    def tools(target) -> list:
        """Select model, neighboring and explicit tool actor addresses."""
        cls = target if isinstance(target, type) else type(target)
        flag = getattr(cls, "__agent__", False)
        conf = flag if isinstance(flag, dict) else {}
        addresses = []
        # 0. Discovery selects capabilities; it never grants execution access.
        if conf.get("self_tools", True):
            addresses.append(getattr(cls, "__tablename__", cls.__name__))
        if conf.get("neighbors", True):
            for _, model in get_fk_list_fields(cls):
                if hasattr(model, "__tablename__"):
                    addresses.append(model.__tablename__)
        addresses.extend(conf.get("tools", []))
        return list(dict.fromkeys(addresses))

    @fullmethod
    def run_config(target, task: str, **kwargs) -> CallConfig:
        """Resolve defaults, model policy and trusted Python call overrides."""
        _validate_options(kwargs)
        cls = target if isinstance(target, type) else type(target)
        flag = getattr(cls, "__agent__", False)
        conf = flag if isinstance(flag, dict) else {}
        # 0. Merge only server-side runtime inputs, independently of routing.
        constraints = dict(config.AGENT_DEFAULTS.get("constraints", {}))
        constraints.update(conf.get("constraints", {}))
        constraints.update(kwargs.get("constraints", {}))
        return CallConfig(
            task=task, prompt=kwargs.get("prompt") or target.ctx(),
            tools=kwargs["tools"] if "tools" in kwargs else target.tools(),
            user=kwargs.get("user"), constraints=constraints,
            result_type=kwargs.get("result_type") or conf.get("result_type"),
            llm=kwargs.get("llm"), has_llm_override="llm" in kwargs,
            scope=kwargs.get("scope"),
        )

    @fullmethod
    async def agentic(
        target, task: str, *, ttx: TTX | None = None, **kwargs,
    ) -> dict:
        """Create or resume an authorized root and execute through Matrix."""
        # 0. Callee admission precedes history, context and provider projection.
        _validate_options(kwargs)
        _authorize_agentic(target, kwargs.get("user"))
        owner = (
            Agent.create_history(
                target, user=kwargs.get("user"), scope=kwargs.get("scope"),
            ) if ttx is None else Agent.authorize_history(
                ttx, user=kwargs.get("user"), action="update",
                scope=kwargs.get("scope"),
            )
        )
        call = target.run_config(task, **kwargs)
        return await Agent.invoke(target, call, ttx=owner)

    @fullmethod
    async def AGENTIC(target, data: dict, tx: TX):
        """Adapt bounded native commands to the callee's guarded run seam."""
        from .threaded_mixin import _ttx_execution

        # 0. Transport caller is authoritative; body identity is ignored.
        if not isinstance(data, dict) or set(data) - {
            "task", "ttx_ref", "id", "scope", "user", "stream",
        }:
            raise ValueError("Unsupported AGENTIC command arguments")
        task = data.get("task")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("AGENTIC requires a nonblank task")
        if "stream" in data and type(data["stream"]) is not bool:
            raise ValueError("AGENTIC stream must be a boolean")
        cls = target if isinstance(target, type) else type(target)
        ident = data.get("id")
        if ident is not None:
            if type(ident) is not int or ident <= 0:
                raise ValueError("AGENTIC requires a positive instance ID")
            target = cls.get(ident)
            if target is None:
                raise ValueError("AGENTIC target is unavailable")
        caller = _caller_user(tx.meta.get("user"))
        _authorize_agentic(target, caller)
        # 1. Reload the declared owner before any overridable configuration.
        owner = Agent.get_history(
            data.get("ttx_ref"), user=caller, action="update",
        )
        owner = Agent.authorize_history(
            owner, user=caller, action="update", scope=data.get("scope"),
        )
        trusted = _trusted_call.get()
        if trusted is None:
            call = target.run_config(task, user=caller, scope=data.get("scope"))
        else:
            address, owner_id, call = trusted
            if (
                not isinstance(call, CallConfig) or owner_id != owner.id
                or address != _agent_addr(target, cls) or address != tx.target
                or call.task != task or _caller_user(call.user) != caller
                or call.scope != data.get("scope")
            ):
                raise ValueError("Trusted AGENTIC call does not match command")
        # 2. Remove ingress metadata before ActorModel creates native replies.
        tx.meta = {
            key: value for key, value in tx.meta.items()
            if key in {"user", "req", "seq", "stream", "stream_end"}
        }
        if data.get("stream", False):

            async def stream():
                """Retain owner context throughout guarded stream iteration."""
                with _ttx_execution(owner):
                    async for chunk in target.run_stream(
                        **call.runtime_args(), ttx=owner,
                    ):
                        if chunk.get("name") in {"done", "error"}:
                            _record_return(target, owner, chunk["data"])
                        yield chunk

            return stream()
        # 3. Run overrides retain whole-business save and validation behavior.
        with _ttx_execution(owner):
            result = await target.run(**call.runtime_args(), ttx=owner)
            _record_return(target, owner, result)
            return result

    @fullmethod
    async def run(
        target, task: str, prompt: str, tools: list,
        user: dict = None, constraints: dict = None, result_type=None,
        scope: Ref | None = None, *, ttx: TTX, **kwargs,
    ) -> dict:
        """Prepare and execute trusted inputs with a mandatory saved owner.

        This is the internal execution seam, not an ingress permission gate.
        Applications override it for fresh domain guards and save behavior."""
        # 0. Preserve backend-selected models, tools, result types and retries.
        _validate_options(kwargs, runtime=True)
        call = CallConfig(
            task=task, prompt=prompt, tools=tools, user=user,
            constraints=constraints or {}, result_type=result_type,
            llm=kwargs.get("llm"), has_llm_override="llm" in kwargs,
            scope=scope,
        )
        prepared = await Agent.prepare(target, call, ttx=ttx)
        return await Agent.run(prepared, task)

    @fullmethod
    async def agentic_stream(
        target, task: str, *, ttx: TTX | None = None, **kwargs,
    ):
        """Create/resume an authorized root and stream through native Matrix."""
        # 0. Apply the same callee/root admission before building context.
        _validate_options(kwargs)
        _authorize_agentic(target, kwargs.get("user"))
        owner = (
            Agent.create_history(
                target, user=kwargs.get("user"), scope=kwargs.get("scope"),
            ) if ttx is None else Agent.authorize_history(
                ttx, user=kwargs.get("user"), action="update",
                scope=kwargs.get("scope"),
            )
        )
        call = target.run_config(task, **kwargs)
        async for chunk in Agent.invoke_stream(target, call, ttx=owner):
            yield chunk

    @fullmethod
    async def run_stream(
        target, task: str, prompt: str, tools: list,
        user: dict = None, constraints: dict = None, result_type=None,
        scope: Ref | None = None, *, ttx: TTX, **kwargs,
    ):
        """Stream the same prepared SDK loop; explicit early close is unsafe."""
        _validate_options(kwargs, runtime=True)
        call = CallConfig(
            task=task, prompt=prompt, tools=tools, user=user,
            constraints=constraints or {}, result_type=result_type,
            llm=kwargs.get("llm"), has_llm_override="llm" in kwargs,
            scope=scope,
        )
        # 0. Retain native error events without another execution/retry loop.
        try:
            prepared = await Agent.prepare(target, call, ttx=ttx)
            async for chunk in Agent.run_stream(prepared, task):
                yield chunk
        except Exception as error:
            yield {
                "name": "error",
                "data": {"message": str(error), "code": 500},
                "meta": {"stream": True, "error": True, "seq": 0},
            }


# Changelog (Python has no block-comment syntax).
# - 2026-11-11: Route all policy calls through native Matrix AGENTIC and guarded
#   run overrides; require TTX state and retain trusted bounded configuration.
# - 2026-11-11: Carry explicit TTX owners through guarded native execution;
#   add a Matrix-only AGENTIC adapter gated by explicit per-callee policy.
#   Preserve legacy callers, context restoration and native streaming.
# - 2026-10-31: Forward explicit business scope through native agent adapters.
#   Normalize documentation and source layout.
