"""Runtime seam for agent preparation and execution."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from pydantic_ai import Agent as PydanticAgent, UsageLimits
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
)

from n3tx_core import config
from n3tx_actors.actor import Actor
from n3tx_actors.tx import TX

from .thread import Thread
from .tools import discover_tools, make_tool
from .utils import _agent_addr, _resolve_llm, _thread_matches_agent, _thread_user


logger = logging.getLogger('n3tx.agents')


@dataclass
class AgentDeps:
    """Context passed to Pydantic AI tool functions via RunContext."""

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

    def runtime_args(self) -> dict:
        args = {
            'task': self.task,
            'prompt': self.prompt,
            'tools': self.tools,
            'user': self.user,
            'constraints': self.constraints,
            'thread_id': self.thread_id,
            'result_type': self.result_type,
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

    @classmethod
    async def _get_thread(cls, root, thread_id, user=None):
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
    async def _create_thread(cls, root, agent_addr: str, user=None, model_cls=None):
        auth_user = _thread_user(user)
        payload = {
            'agent_addr': agent_addr or getattr(model_cls, '__tablename__', model_cls.__name__),
            'messages': [],
        }
        if isinstance(auth_user, dict) and auth_user.get('user_id') is not None:
            payload['user_owner'] = auth_user['user_id']

        create_tx = TX(
            name='create', source=root.addr, target='threads',
            data=payload,
            meta={'user': auth_user} if auth_user else {},
        )
        create_resp = await root.request(create_tx)
        if create_resp.is_error:
            raise RuntimeError(
                "Failed to create thread: "
                f"{create_resp.data.get('message', 'unknown error')}"
            )
        return create_resp.data

    @classmethod
    async def _load_or_create_thread(cls, root, agent_addr: str, user=None,
                                     thread_id=None, model_cls=None):
        thread_data = None
        if thread_id is not None:
            thread_data = await cls._get_thread(root, thread_id, user=user)
            if not _thread_matches_agent(thread_data, agent_addr, cls=model_cls):
                raise RuntimeError(
                    f"Thread {thread_id} belongs to {thread_data.get('agent_addr', 'another agent')}, "
                    f"not {agent_addr or getattr(model_cls, '__tablename__', model_cls.__name__)}"
                )
        else:
            thread_data = await cls._create_thread(root, agent_addr, user=user, model_cls=model_cls)
            thread_id = thread_data.get('id')

        message_history = None
        if thread_data is not None:
            message_history = Thread.to_history(thread_data.get('messages', []))

        return thread_data, thread_id, message_history

    @classmethod
    async def _update_thread(cls, root, thread_id, all_messages, user=None, source='', target=''):
        auth_user = _thread_user(user)
        update_tx = TX(
            name='update', source=root.addr, target='threads',
            data={
                'id': thread_id,
                'messages': Thread.from_history(
                    all_messages,
                    source=source,
                    target=target,
                ),
            },
            meta={'user': auth_user} if auth_user else {},
        )
        update_resp = await root.request(update_tx)
        if update_resp.is_error:
            logger.warning(
                "Failed to update thread %s: %s",
                thread_id,
                update_resp.data.get('message', 'unknown'),
            )

    @classmethod
    async def prepare(cls, target, call: 'CallConfig') -> PreparedCall:
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

        _, thread_id, message_history = await cls._load_or_create_thread(
            root=root,
            agent_addr=agent_addr,
            user=call.user,
            thread_id=call.thread_id,
            model_cls=model_cls,
        )

        tool_specs = discover_tools(call.tools, root, caller_addr=agent_addr)
        if not tool_specs:
            logger.warning(
                "[%s] No tools discovered from addresses: %s", agent_addr, call.tools
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
    async def call(cls, prepared: PreparedCall, task: str) -> dict:
        run_kwargs = {'deps': prepared.deps}
        if prepared.usage_limits:
            run_kwargs['usage_limits'] = prepared.usage_limits
        if prepared.message_history:
            run_kwargs['message_history'] = prepared.message_history

        result = await prepared.ai_agent.run(task, **run_kwargs)

        usage = result.usage()
        all_messages = result.all_messages()

        if prepared.thread_id is not None:
            await cls._update_thread(
                root=prepared.root,
                thread_id=prepared.thread_id,
                all_messages=all_messages,
                user=prepared.deps.user,
                source=prepared.root.addr,
                target=prepared.agent_addr,
            )

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

    @classmethod
    async def call_stream(cls, prepared: PreparedCall, task: str):
        seq = 0
        try:
            run_kwargs = {'deps': prepared.deps}
            if prepared.usage_limits:
                run_kwargs['usage_limits'] = prepared.usage_limits
            if prepared.message_history:
                run_kwargs['message_history'] = prepared.message_history

            streamed_text = ''
            tool_call_count = 0

            async with prepared.ai_agent.iter(task, **run_kwargs) as agent_run:
                async for node in agent_run:
                    if isinstance(node, ModelRequestNode):
                        async with node.stream(agent_run.ctx) as request_stream:
                            async for event in request_stream:
                                if isinstance(event, PartStartEvent):
                                    if isinstance(event.part, ToolCallPart):
                                        tool_call_count += 1
                                        args = event.part.args
                                        if isinstance(args, str):
                                            try:
                                                args = json.loads(args)
                                            except (json.JSONDecodeError, TypeError):
                                                args = {'raw': args}
                                        yield {
                                            'name': 'tool_call',
                                            'data': {
                                                'tool': event.part.tool_name,
                                                'args': args,
                                                'call_id': event.part.tool_call_id,
                                            },
                                            'meta': {'stream': True, 'seq': seq},
                                        }
                                        seq += 1
                                    elif isinstance(event.part, ThinkingPart):
                                        if event.part.content:
                                            yield {
                                                'name': 'thinking',
                                                'data': {'text': event.part.content},
                                                'meta': {'stream': True, 'seq': seq},
                                            }
                                            seq += 1
                                    elif isinstance(event.part, TextPart):
                                        if event.part.content:
                                            streamed_text += event.part.content
                                            yield {
                                                'name': 'text',
                                                'data': {'text': event.part.content},
                                                'meta': {'stream': True, 'seq': seq},
                                            }
                                            seq += 1
                                elif isinstance(event, PartDeltaEvent):
                                    if isinstance(event.delta, TextPartDelta):
                                        streamed_text += event.delta.content_delta
                                        yield {
                                            'name': 'text',
                                            'data': {'text': event.delta.content_delta},
                                            'meta': {'stream': True, 'seq': seq},
                                        }
                                        seq += 1
                                    elif isinstance(event.delta, ThinkingPartDelta):
                                        yield {
                                            'name': 'thinking',
                                            'data': {'text': event.delta.content_delta},
                                            'meta': {'stream': True, 'seq': seq},
                                        }
                                        seq += 1
                    elif isinstance(node, CallToolsNode):
                        async with node.stream(agent_run.ctx) as tools_stream:
                            async for event in tools_stream:
                                if isinstance(event, FunctionToolResultEvent):
                                    yield {
                                        'name': 'tool_result',
                                        'data': {
                                            'tool': event.result.tool_name,
                                            'result': str(event.result.content),
                                            'call_id': event.result.tool_call_id,
                                        },
                                        'meta': {'stream': True, 'seq': seq},
                                    }
                                    seq += 1

                run_result = agent_run.result
                usage = agent_run.usage()
                output = run_result.output if run_result else ''
                if not output and streamed_text:
                    output = streamed_text
                all_messages = agent_run.all_messages()

                if prepared.thread_id is not None:
                    await cls._update_thread(
                        root=prepared.root,
                        thread_id=prepared.thread_id,
                        all_messages=all_messages,
                        user=prepared.deps.user,
                        source=prepared.root.addr,
                        target=prepared.agent_addr,
                    )

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
