"""Runtime seam for agent preparation and execution.

Thread records are ground truth; provider-context reconciliation must remain
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
from n3tx_actors.tx import TX
from n3tx_core.models.ref import Ref, local_ref_id

from .thread import HISTORY_CODEC, Thread
from .tools import discover_tools, make_tool
from .utils import _agent_addr, _resolve_llm, _thread_user


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
    thread_id: int | None
    message_history: list | None
    ai_agent: PydanticAgent
    deps: AgentDeps
    usage_limits: UsageLimits | None


class Agent:
    """Internal runtime owner for prepared agent execution."""

    @staticmethod
    def _value_or_call(obj, name, default=None):
        """Read native result attributes across callable/property variants."""
        value = getattr(obj, name, default)
        return value() if callable(value) else value

    @classmethod
    async def _get_thread(cls, root, thread_id, user=None):
        """Read one exact Thread through its existing Matrix authorization."""
        # 0. Preserve native caller propagation and actor authorization.
        auth_user = _thread_user(user)
        thread_tx = TX(
            name='get', source=root.addr, target='threads',
            data={'id': thread_id},
            meta={'user': auth_user} if auth_user else {},
        )
        thread_resp = await root.request(thread_tx)
        if thread_resp.is_error:
            raise RuntimeError(
                f"Thread {thread_id} not found or access denied: "
                f"{thread_resp.data.get('message', 'unknown error')}"
            )
        return thread_resp.data

    @classmethod
    async def _create_thread(cls, root, scope: Ref | None = None, user=None):
        """Create Thread metadata through native Matrix authorization."""
        # 0. Derive ownership from the native caller, not a payload argument.
        auth_user = _thread_user(user)
        payload = {'scope': Ref(scope) if scope is not None else None}
        if isinstance(auth_user, dict) and auth_user.get('user_id') is not None:
            payload['user_owner'] = auth_user['user_id']
        # 1. Retain the native request and response contract.
        create_tx = TX(
            name='create', source=root.addr, target='threads', data=payload,
            meta={'user': auth_user} if auth_user else {},
        )
        create_resp = await root.request(create_tx)
        if create_resp.is_error:
            raise RuntimeError(
                'Failed to create thread: '
                f"{create_resp.data.get('message', 'unknown error')}"
            )
        return create_resp.data

    @classmethod
    async def _load_or_create_thread(
        cls, root, scope: Ref | None = None, user=None, thread_id=None,
    ):
        """Load record-backed history for a native saved or new Thread."""
        # 0. Use the existing native Matrix read/create path.
        if thread_id is not None:
            thread_data = await cls._get_thread(root, thread_id, user=user)
        else:
            thread_data = await cls._create_thread(root, scope, user=user)
            thread_id = thread_data.get('id')
        # 1. Decode protocol records rather than a persisted message array.
        thread = Thread.model_validate(thread_data)
        history = thread.history(user=_thread_user(user))
        return thread_data, thread_id, history

    @classmethod
    def _persist_new_messages(
        cls, prepared: PreparedCall, messages: list, *, cursor: int,
    ) -> int:
        """Append finalized messages and return the last successful position.

        Failure leaves the successful prefix intact. The caller must stop
        checkpointing after a short append. Uncertain writes are not retried."""
        # 0. Serialize only the finalized suffix beyond the saved position.
        try:
            thread = Thread.get(prepared.thread_id)
            suffix = ModelMessagesTypeAdapter.dump_python(
                messages[cursor:], mode='json',
            )
            # 1. Advance after each successful ordinary native append.
            for message in suffix:
                thread.append(TX(
                    name=message['kind'], source=prepared.root.addr,
                    target=prepared.agent_addr, data=message,
                    meta={'codec': HISTORY_CODEC},
                ), user=_thread_user(prepared.deps.user))
                cursor += 1
        except Exception as error:
            logger.warning(
                'Thread %s append failed (%s)',
                prepared.thread_id, type(error).__name__,
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
            if failed or prepared.thread_id is None or len(messages) <= cursor:
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
    async def prepare(cls, target, call: 'CallConfig') -> PreparedCall:
        """Prepare one native agent with record-backed protocol history."""
        # 0. Resolve runtime routing/provider inputs, not persisted authority.
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
        # 1. Load native history and carry scope only as creation metadata.
        scope = Ref(call.scope) if call.scope is not None else None
        _, thread_id, message_history = await cls._load_or_create_thread(
            root=root,
            scope=scope,
            user=call.user,
            thread_id=call.thread_id,
        )
        # Link this invocation's history with an explicit parent THREAD TX.
        from .threaded_mixin import current_execution
        execution = current_execution.get()
        if execution is not None:
            parent_id = local_ref_id(
                execution.meta["thread"], target_cls=Thread,
            )
            parent = Thread.get(parent_id)
            parent.THREAD(Thread.get(thread_id), user=_thread_user(call.user))
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

        ai_agent = PydanticAgent(llm, **agent_kwargs)

        deps = AgentDeps(
            user=call.user,
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
            thread_id=thread_id,
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
        if prepared.thread_id is not None:
            result_dict['thread_id'] = prepared.thread_id
        return result_dict

    call = run

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
                }
                if prepared.thread_id is not None:
                    done_data['thread_id'] = prepared.thread_id

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

    call_stream = run_stream


# Changelog (Python has no block-comment syntax):
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
