"""Agent — native preparation, SDK execution and protocol-history decoding.

API surface:
    CallConfig / PreparedCall — Normalized inputs and prepared SDK state
    AgentDeps                — Trusted caller and tool-routing inputs
    Agent.prepare/run        — One SDK loop with mandatory canonical TTX state
    Agent.invoke             — Native Matrix AGENTIC with trusted CallConfig
    Agent.run_stream         — Native streaming with finalized checkpoints
    Agent.chat_history       — Decode incoming codec-tagged TTX messages

Boundary: history.py owns agent-root policy and full SDK decoding. Entry
adapters separately own callee authorization and fresh business execution
guards. Trusted configuration crosses Matrix in task-local Python state, never
in client command data, persisted metadata or transport replies.

Stored records are ground truth; provider-context reconciliation stays in
memory. Explicit early aclose() of run_stream is unsupported with the installed
SDK: cleanup can fail and interrupted history may be incomplete. Closing a
stream does not establish rollback and must not trigger replay."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional

from pydantic_ai import Agent as PydanticAgent, UsageLimits
from pydantic_ai.capabilities import Hooks
from pydantic_ai._agent_graph import ModelRequestNode, CallToolsNode
from pydantic_ai.messages import (
    PartStartEvent,
    PartDeltaEvent,
    TextPart,
    ToolCallPart,
    ThinkingPart,
    TextPartDelta,
    ThinkingPartDelta,
    FunctionToolResultEvent,
    ModelMessagesTypeAdapter,
    repair_messages,
)

from n3tx_core import config
from n3tx_actors.actor import Actor
from n3tx_actors.tx import TX
from n3tx_core.models.ref import Ref, public_id_url
from n3tx_core.utils.erroring import MethodError
from n3tx_threads import TTX

from .history import (
    HISTORY_CODEC, authorize_history, chat_history, create_history, get_history,
)
from .tools import discover_tools, make_tool
from .utils import _agent_addr, _resolve_llm, _caller_user


logger = logging.getLogger('n3tx.agents')


@dataclass
class AgentDeps:
    """Trusted caller/routing inputs for Pydantic AI tools."""

    user: Optional[dict]
    agent_addr: str
    ttx: TTX


@dataclass(frozen=True)
class CallConfig:
    """Trusted execution inputs shared by policy adapters and the SDK runtime.

    runtime_args preserves explicit backend model/tool/output/retry choices.
    Nullable scope is compatibility metadata, never a permission grant."""

    task: str
    prompt: str
    tools: list
    user: dict | None
    constraints: dict
    result_type: Any = None
    llm: Any = None
    has_llm_override: bool = False
    scope: Ref | None = None

    def runtime_args(self) -> dict:
        """Forward trusted adapter inputs without exposing runtime callbacks."""
        # 0. Keep scope independent of routing and preserve explicit overrides.
        args = {
            'task': self.task,
            'prompt': self.prompt,
            'tools': self.tools,
            'user': self.user,
            'constraints': self.constraints,
            'result_type': self.result_type,
            'scope': self.scope,
        }
        if self.has_llm_override:
            args['llm'] = self.llm
        return args


@dataclass(frozen=True)
class PreparedCall:
    """Execution-ready SDK state with one mandatory canonical history owner."""

    root: Actor
    agent_addr: str
    message_history: list | None
    ai_agent: PydanticAgent
    deps: AgentDeps
    usage_limits: UsageLimits | None
    ttx: TTX


_trusted_call: ContextVar[tuple | None] = ContextVar(
    "native_agent_call", default=None,
)


class Agent:
    """Own native SDK preparation, execution and protocol-history decoding.

    API: prepare builds SDK state; run/run_stream checkpoint finalized messages.
    History helpers enforce agent-root policy or decode incoming SDK records.
    invoke/invoke_stream preserve trusted inputs through native Matrix routing.
    Entry adapters retain provider selection, scope checks and execution guards;
    this class adds no alternate dispatcher, history container or retry loop."""

    create_history = staticmethod(create_history)
    get_history = staticmethod(get_history)
    authorize_history = staticmethod(authorize_history)
    chat_history = staticmethod(chat_history)

    @staticmethod
    def _value_or_call(obj, name, default=None):
        """Read native result attributes across callable/property variants."""
        value = getattr(obj, name, default)
        return value() if callable(value) else value

    @classmethod
    def _command(cls, target, call: CallConfig, ttx: TTX, *, stream=False):
        """Build native arguments without serializing runtime configuration."""
        # 0. Reauthorize the exact owner before Matrix and provider admission.
        owner = cls.authorize_history(
            ttx, user=call.user, action="update", scope=call.scope,
        )
        model = target if isinstance(target, type) else type(target)
        address = _agent_addr(target, model)
        data = {
            "task": call.task,
            "ttx_ref": public_id_url(owner.id, target_cls=TTX),
            "scope": call.scope,
        }
        if not isinstance(target, type) and getattr(target, "id", 0):
            data["id"] = target.id
        if stream:
            data["stream"] = True
        root = Actor.root()
        if root is None:
            raise RuntimeError("No Matrix root is available")
        return root, TX(
            "AGENTIC", f"ttx/{owner.id}", address, data=data,
            meta={"user": _caller_user(call.user)},
        )

    @classmethod
    async def invoke(cls, target, call: CallConfig, *, ttx: TTX) -> dict:
        """Invoke guarded callee run through Matrix with trusted inputs."""
        # 0. Task-local state cannot be supplied through client command data.
        root, command = cls._command(target, call, ttx)
        token = _trusted_call.set((command.target, ttx.id, call))
        try:
            response = await root.request(command)
        finally:
            _trusted_call.reset(token)
        # 1. Preserve native semantic errors without retrying uncertain effects.
        if response.is_error:
            raise MethodError(
                response.data.get("message", "Agent invocation failed"),
                response.data.get("code", 500),
            )
        return response.data

    @classmethod
    async def invoke_stream(cls, target, call: CallConfig, *, ttx: TTX):
        """Yield guarded native Matrix events with the same trusted call."""
        root, command = cls._command(target, call, ttx, stream=True)
        token = _trusted_call.set((command.target, ttx.id, call))
        try:
            # 0. Native Matrix owns streaming correlation and cancellation.
            async for response in root.stream(command):
                if response.is_error:
                    raise MethodError(
                        response.data.get("message", "Agent stream failed"),
                        response.data.get("code", 500),
                    )
                if response.data:
                    yield response.data
        finally:
            _trusted_call.reset(token)

    @classmethod
    def _persist_new_messages(
        cls, prepared: PreparedCall, messages: list, *, cursor: int,
    ) -> int:
        """Append finalized messages and return the last successful position.

        Failure leaves the successful prefix intact. The caller must stop
        checkpointing after a short append. Uncertain writes are not retried."""
        # 0. Serialize only the finalized suffix beyond the saved position.
        try:
            owner = cls.authorize_history(
                prepared.ttx, user=prepared.deps.user, action="update",
            )
            suffix = ModelMessagesTypeAdapter.dump_python(
                messages[cursor:], mode='json',
            )
            # 1. Advance after each successful ordinary native append.
            for message in suffix:
                envelope = TX(
                    name=message['kind'], source=f"ttx/{owner.id}",
                    target=prepared.agent_addr, data=message,
                    meta={'codec': HISTORY_CODEC},
                )
                owner.ATTACH(TTX.from_tx(envelope))
                cursor += 1
        except Exception as error:
            logger.warning(
                'History %s append failed (%s)',
                f"ttx/{prepared.ttx.id}", type(error).__name__,
            )
        return cursor

    @classmethod
    def _history_hooks(cls, prepared: PreparedCall):
        """Create per-invocation checkpoints without changing SDK streaming."""
        # 0. Count only this run's new messages, never the normalized prefix.
        cursor = 0
        failed = False

        def flush(messages: list) -> None:
            """Append new run messages unless persistence already failed."""
            nonlocal cursor, failed
            if failed or len(messages) <= cursor:
                return
            cursor = cls._persist_new_messages(
                prepared, messages, cursor=cursor,
            )
            failed = cursor != len(messages)

        async def checkpoint(ctx, *, node, handler):
            """Save finalized messages tagged by the SDK with this run ID."""
            try:
                return await handler(node)
            finally:
                if ctx.run_id is not None:
                    flush([
                        message for message in ctx.messages
                        if message.run_id == ctx.run_id
                    ])

        return Hooks(node_run=checkpoint), flush

    @classmethod
    async def prepare(
        cls, target, call: 'CallConfig', *, ttx: TTX,
    ) -> PreparedCall:
        """Prepare one SDK agent with mandatory authorized TTX history."""
        # 0. History admission precedes history reads and provider resolution.
        owner = cls.authorize_history(
            ttx, user=call.user, action="update", scope=call.scope,
        )
        message_history = cls.chat_history(owner)
        # 1. Resolve runtime routing/provider inputs, not persisted authority.
        model_cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(model_cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}

        llm = _resolve_llm(
            call.llm if call.has_llm_override else (
                model_conf.get('llm')
                or getattr(target, 'llm', None)
                or config.AGENT_DEFAULTS.get('llm')
            )
        )

        agent_addr = _agent_addr(target, model_cls)

        root = Actor.root()
        if not root:
            raise RuntimeError(
                "No Matrix root. Initialize a Matrix before running agents."
            )
        # 2. Reuse native tool discovery, Pydantic AI and request limits.
        tool_specs = discover_tools(call.tools, root, caller_addr=agent_addr)
        if not tool_specs:
            logger.warning(
                "[%s] No tools discovered from addresses: %s",
                agent_addr, call.tools,
            )
        ai_tools = [make_tool(spec) for spec in tool_specs]

        agent_kwargs = {
            'system_prompt': call.prompt,
            'deps_type': AgentDeps,
            'tools': ai_tools,
        }
        if call.result_type:
            agent_kwargs['output_type'] = call.result_type
        retries = {}
        for key, sdk_key in (
            ("tool_retries", "tools"), ("output_retries", "output"),
        ):
            if key in call.constraints:
                retries[sdk_key] = call.constraints[key]
        if retries:
            agent_kwargs['retries'] = retries

        ai_agent = PydanticAgent(llm, **agent_kwargs)

        deps = AgentDeps(
            user=_caller_user(call.user),
            agent_addr=agent_addr,
            ttx=owner,
        )

        usage_limits = None
        if call.constraints.get('max_iterations'):
            usage_limits = UsageLimits(
                request_limit=call.constraints['max_iterations'],
            )

        return PreparedCall(
            root=root,
            agent_addr=agent_addr,
            message_history=message_history,
            ai_agent=ai_agent,
            deps=deps,
            usage_limits=usage_limits,
            ttx=owner,
        )

    @classmethod
    async def run(cls, prepared: PreparedCall, task: str) -> dict:
        """Execute with reconciled context, returning raw evidence plus output.

        Stored history is never rewritten. Returned messages combine the raw
        loaded prefix with new SDK messages for exact persistence verification;
        they are not the SDK's normalized full-context projection."""
        # 0. Reconcile only a copy; keep recorded evidence out of SDK mutation.
        hooks, flush = cls._history_hooks(prepared)
        run_kwargs = {'deps': prepared.deps, 'capabilities': [hooks]}
        if prepared.usage_limits:
            run_kwargs['usage_limits'] = prepared.usage_limits
        if prepared.message_history:
            run_kwargs['message_history'] = repair_messages(
                deepcopy(prepared.message_history),
            )

        from .threaded_mixin import _ttx_execution
        with _ttx_execution(prepared.ttx):
            result = await prepared.ai_agent.run(task, **run_kwargs)

        usage = cls._value_or_call(result, 'usage')
        new_messages = result.new_messages()
        # 1. Flush final protocol completion without replaying execution.
        flush(new_messages)
        # 2. Preserve the native result contract for independent host auditing.
        all_messages = [*(prepared.message_history or []), *new_messages]
        result_dict = {
            'answer': result.output,
            'usage': {
                'input_tokens': usage.input_tokens,
                'output_tokens': usage.output_tokens,
                'requests': usage.requests,
            },
            'messages': all_messages,
            'message_count': len(all_messages),
        }
        result_dict['ttx_ref'] = public_id_url(prepared.ttx.id, target_cls=TTX)
        return result_dict

    @classmethod
    async def run_stream(cls, prepared: PreparedCall, task: str):
        """Stream native events and checkpoint finalized protocol history.

        Explicit early aclose() is unsupported: the installed SDK can fail
        async-generator cleanup and leave history incomplete. Normal completion
        and tested cancellation paths are distinct; neither implies rollback.
        Do not drain more tools or retry execution to compensate for closing."""
        # 0. Reuse the prepared native loop and its existing event vocabulary.
        seq = 0
        agent_run = None
        flush = None
        from .threaded_mixin import current_execution
        token = current_execution.set(prepared.ttx)
        try:
            hooks, flush = cls._history_hooks(prepared)
            run_kwargs = {'deps': prepared.deps, 'capabilities': [hooks]}
            if prepared.usage_limits:
                run_kwargs['usage_limits'] = prepared.usage_limits
            if prepared.message_history:
                run_kwargs['message_history'] = repair_messages(
                    deepcopy(prepared.message_history),
                )

            streamed_text = ''
            tool_call_count = 0

            async with prepared.ai_agent.iter(task, **run_kwargs) as agent_run:
                async for node in agent_run:
                    if isinstance(node, ModelRequestNode):
                        async with node.stream(agent_run.ctx) as request_stream:
                            async for event in request_stream:
                                meta = {'stream': True, 'seq': seq}
                                if isinstance(event, PartStartEvent):
                                    if isinstance(event.part, ToolCallPart):
                                        tool_call_count += 1
                                        args = event.part.args
                                        if isinstance(args, str):
                                            try:
                                                args = json.loads(args)
                                            except (
                                                json.JSONDecodeError, TypeError,
                                            ):
                                                args = {'raw': args}
                                        call_id = event.part.tool_call_id
                                        yield {
                                            'name': 'tool_call',
                                            'data': {
                                                'tool': event.part.tool_name,
                                                'args': args,
                                                'call_id': call_id,
                                            },
                                            'meta': meta,
                                        }
                                        seq += 1
                                    elif isinstance(event.part, ThinkingPart):
                                        if event.part.content:
                                            text = event.part.content
                                            yield {
                                                'name': 'thinking',
                                                'data': {'text': text},
                                                'meta': meta,
                                            }
                                            seq += 1
                                    elif isinstance(event.part, TextPart):
                                        if event.part.content:
                                            text = event.part.content
                                            streamed_text += text
                                            yield {
                                                'name': 'text',
                                                'data': {'text': text},
                                                'meta': meta,
                                            }
                                            seq += 1
                                elif isinstance(event, PartDeltaEvent):
                                    if isinstance(event.delta, TextPartDelta):
                                        text = event.delta.content_delta
                                        streamed_text += text
                                        yield {
                                            'name': 'text',
                                            'data': {'text': text},
                                            'meta': meta,
                                        }
                                        seq += 1
                                    elif isinstance(
                                        event.delta, ThinkingPartDelta,
                                    ):
                                        text = event.delta.content_delta
                                        yield {
                                            'name': 'thinking',
                                            'data': {'text': text},
                                            'meta': meta,
                                        }
                                        seq += 1
                    elif isinstance(node, CallToolsNode):
                        async with node.stream(agent_run.ctx) as tools_stream:
                            async for event in tools_stream:
                                if isinstance(event, FunctionToolResultEvent):
                                    result_part = (
                                        getattr(event, 'result', None)
                                        or getattr(event, 'part', None)
                                    )
                                    tool_name = getattr(
                                        result_part, 'tool_name', '',
                                    )
                                    content = getattr(
                                        result_part, 'content',
                                        getattr(event, 'content', ''),
                                    )
                                    call_id = getattr(
                                        result_part, 'tool_call_id',
                                        getattr(event, 'tool_call_id', ''),
                                    )
                                    yield {
                                        'name': 'tool_result',
                                        'data': {
                                            'tool': tool_name,
                                            'result': str(content),
                                            'call_id': call_id,
                                        },
                                        'meta': {'stream': True, 'seq': seq},
                                    }
                                    seq += 1

                run_result = agent_run.result
                usage = cls._value_or_call(agent_run, 'usage')
                output = run_result.output if run_result else ''
                if not output and streamed_text:
                    output = streamed_text
                # 1. Flush final protocol completion before the done event.
                flush(agent_run.new_messages())
                # 2. Preserve native completion; host effects remain separate.
                done_data = {
                    'answer': str(output),
                    'usage': {
                        'input_tokens': usage.input_tokens,
                        'output_tokens': usage.output_tokens,
                        'requests': usage.requests,
                    },
                    'tool_calls': tool_call_count,
                }
                done_data['ttx_ref'] = public_id_url(
                    prepared.ttx.id, target_cls=TTX,
                )

                yield {
                    'name': 'done',
                    'data': done_data,
                    'meta': {
                        'stream': True,
                        'stream_end': True,
                        'seq': seq,
                    },
                }

        except Exception as e:
            yield {
                'name': 'error',
                'data': {'message': str(e), 'code': 500},
                'meta': {'stream': True, 'error': True, 'seq': seq},
            }
        finally:
            # 3. Stream teardown finalizes interrupted model/tool messages.
            try:
                if agent_run is not None and flush is not None:
                    flush(agent_run.new_messages())
            finally:
                current_execution.reset(token)


# Changelog (Python has no block-comment syntax):
# - 2026-11-11: Require TTX throughout preparation, dependencies and results;
#   remove legacy journals/aliases and retain one SDK checkpoint loop.
#   Add Matrix invocation with task-local trusted configuration and retries.
# - 2026-11-11: Add trusted TTX SDK-history decoding with codec selection and
#   insertion ordering; retain legacy preparation and checkpoint behavior.
#   Add explicit scope-authorized TTX preparation and ATTACH checkpoints while
#   retaining legacy identities; select one journal and return canonical refs.
# - 2026-10-31: Reconcile SDK context in memory; append only new run messages.
# - 2026-10-31: Document unsupported explicit early stream close and its risks.
# - 2026-10-31: Checkpoint finalized history; remove observer dependencies.
# - 2026-10-31: Append scoped protocol suffixes against an atomic history basis.
#   Preserve native execution and add trusted tool observation dependencies.
#   Reauthorize before inference and retain run-wide observation failure.
#   Bound complete output history and use the distinct record-auth hook.
#   Use native scope ACLs and recheck source read/update before inference.
#   Authorize server-built Thread drafts before trusted native creation.
#   Restore native owner/admin routing and ordinary suffix persistence.
#   Remove basis, output-limit, scope-policy and observation-latch guards.
#   Serialize new protocol messages directly with the native message adapter.
