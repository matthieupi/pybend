"""Runtime seam for agent preparation and execution.

TTX messages are ground truth; provider-context reconciliation must remain
in memory. Explicit early aclose() of run_stream is unsupported with the
installed SDK: cleanup can fail and the interrupted history may be incomplete.
Closing a stream does not establish rollback and must not trigger replay."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
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
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.models.ref import Ref, public_id_url
from n3tx_core.utils.registrar import registered_models
from n3tx_threads import Thread, TTX

from .history import _authorize_thread, open_thread, read_history
from .tools import discover_tools, make_tool
from .utils import _agent_addr, _normalize_user, _resolve_llm


logger = logging.getLogger('n3tx.agents')


@dataclass
class AgentDeps:
    """Trusted caller/routing inputs for Pydantic AI tools."""

    user: Optional[dict]
    agent_addr: str


@dataclass(frozen=True)
class CallConfig:
    """Normalized call inputs shared by adapters and runtime."""

    task: str
    prompt: str
    tools: list
    user: dict | None
    constraints: dict
    thread_id: int | None
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
            'thread_id': self.thread_id,
            'result_type': self.result_type,
            'scope': self.scope,
        }
        if self.has_llm_override:
            args['llm'] = self.llm
        return args


@dataclass(frozen=True)
class PreparedCall:
    """Execution-ready runtime state for one agent call."""

    root: Actor
    agent_addr: str
    thread: Thread
    message_history: list
    ai_agent: PydanticAgent
    deps: AgentDeps
    usage_limits: UsageLimits | None


class Agent:
    """Internal runtime owner for prepared agent execution."""

    @staticmethod
    def _value_or_call(obj, name, default=None):
        """Read native result attributes across callable/property variants."""
        # 0. Resolve the SDK attribute and normalize its access convention.
        value = getattr(obj, name, default)
        return value() if callable(value) else value

    @classmethod
    def _persist_new_messages(
        cls, prepared: PreparedCall, messages: list, *, cursor: int,
    ) -> int:
        """Append finalized messages and return the last successful position.

        Failure leaves the successful prefix intact. The caller must stop
        checkpointing after a short append. Uncertain writes are not retried."""
        # 0. Serialize only the finalized suffix beyond the saved position.
        try:
            user = _normalize_user(prepared.deps.user)
            suffix = ModelMessagesTypeAdapter.dump_python(
                messages[cursor:], mode='json',
            )
            # 1. Advance after each successful ordinary native append.
            for message in suffix:
                thread = _authorize_thread(
                    prepared.thread, user=user, action='update',
                )
                thread.APPEND(TX(
                    name='Message', source=prepared.agent_addr,
                    target=public_id_url(thread.id, target_cls=TTX),
                    data=message,
                ), user_owner=user.get('user_id'))
                cursor += 1
        except Exception as error:
            logger.warning(
                'Thread %s append failed (%s)',
                prepared.thread.id, type(error).__name__,
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
            # 0. Retain a successful-prefix cursor and stop after uncertainty.
            nonlocal cursor, failed
            if failed or len(messages) <= cursor:
                return
            cursor = cls._persist_new_messages(
                prepared, messages, cursor=cursor,
            )
            failed = cursor != len(messages)

        async def checkpoint(ctx, *, node, handler):
            """Save finalized messages tagged by the SDK with this run ID."""
            # 0. Preserve execution while flushing this run's finalized prefix.
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
    async def prepare(cls, target, call: 'CallConfig') -> PreparedCall:
        """Authorize a saved owner and history before provider/tool preparation.

        Only a registered, saved ActorModel instance supplies implicit scope.
        Other targets require explicit local business ownership. Resumption
        checks the exact root and owner, while allowing explicit agent handoffs.
        Missing caller identity remains anonymous for history and tools."""
        # 0. Derive implicit ownership only from a registered stored instance.
        model_cls = target if isinstance(target, type) else target.__class__
        scope = call.scope
        if scope is None:
            if (
                not isinstance(target, ActorModel)
                or not getattr(model_cls, '__storable__', False)
                or model_cls not in registered_models.values()
                or type(target.id) is not int
                or target.id <= 0
            ):
                raise ValueError("Agent calls require a saved business scope")
            scope = Ref(public_id_url(target.id, target_cls=model_cls))
        user = _normalize_user(call.user)
        agent_addr = _agent_addr(target, model_cls)
        root = Actor.root()
        if not root:
            raise RuntimeError(
                "No Matrix root. Initialize a Matrix before running agents."
            )
        # 1. Resolve the saved owner and authorize before decoding or providers.
        thread = open_thread(
            scope=Ref(scope), agent_addr=agent_addr, user=user,
            thread_id=call.thread_id,
        )
        message_history = read_history(thread, user=user)
        # 2. Reuse native provider selection, tool discovery and request limits.
        agent_flag = getattr(model_cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}

        llm = _resolve_llm(
            call.llm if call.has_llm_override else (
                model_conf.get('llm')
                or getattr(target, 'llm', None)
                or config.AGENT_DEFAULTS.get('llm')
            )
        )

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

        ai_agent = PydanticAgent(llm, **agent_kwargs)

        deps = AgentDeps(
            user=user,
            agent_addr=agent_addr,
        )

        usage_limits = None
        if call.constraints.get('max_iterations'):
            usage_limits = UsageLimits(
                request_limit=call.constraints['max_iterations'],
            )

        return PreparedCall(
            root=root,
            agent_addr=agent_addr,
            thread=thread,
            message_history=message_history,
            ai_agent=ai_agent,
            deps=deps,
            usage_limits=usage_limits,
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

        result = await prepared.ai_agent.run(task, **run_kwargs)

        usage = cls._value_or_call(result, 'usage')
        new_messages = result.new_messages()
        # 1. Flush final protocol completion without replaying execution.
        flush(new_messages)
        # 2. Preserve the native result contract for independent host auditing.
        all_messages = [*prepared.message_history, *new_messages]
        result_dict = {
            'answer': result.output,
            'usage': {
                'input_tokens': usage.input_tokens,
                'output_tokens': usage.output_tokens,
                'requests': usage.requests,
            },
            'messages': all_messages,
            'message_count': len(all_messages),
            'thread_id': prepared.thread.id,
        }
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
                    'thread_id': prepared.thread.id,
                }

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
            if agent_run is not None and flush is not None:
                flush(agent_run.new_messages())


# Changelog (Python has no block-comment syntax):
# - 2026-11-04: Prepare parent-authorized TTX conversation roots; checkpoint
#   Message children with fresh owner checks and canonical TTX targets.
#   Remove legacy thread CRUD, codecs, implicit capture and unused call aliases.
# - 2026-11-02: Use standalone threads and the agent-owned history decoder.
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
