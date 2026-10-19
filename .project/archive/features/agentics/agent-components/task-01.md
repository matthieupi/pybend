# Rewrite run_stream() to use agent.iter() with typed events

**ID:** task-01 | **Wave:** 1 | **Depends on:** none

## Intent

The current run_stream() only emits 'text' chunks via stream_text(delta=True), hiding tool calls, thinking tokens, and intermediate results from the user. Rewriting to use pydantic-ai's agent.iter() graph API gives full visibility into each step of agent reasoning, yielding typed events (text, tool_call, tool_result, thinking) that frontend components can render differently.

## Context

AgentMixin lives in packages/n3tx-agents/src/n3tx_agents/mixin.py. The run_stream() method (lines 453-621) is a @fullmethod that yields TX-aligned dicts. It currently uses `ai_agent.run_stream(task, **run_kwargs)` with `result.stream_text(delta=True)` which only gives text deltas.

The pydantic-ai agent.iter() API (v1.66+) provides graph-level iteration:
- `async with agent.iter(task, **kwargs) as run` creates an AgentRun
- `async for node in run` yields UserPromptNode, ModelRequestNode, CallToolsNode, End
- `node.stream(run.ctx)` on ModelRequestNode yields: PartStartEvent, PartDeltaEvent, PartEndEvent, FinalResultEvent
  - PartStartEvent.part can be TextPart, ToolCallPart, ThinkingPart
  - PartDeltaEvent.delta can be TextPartDelta, ThinkingPartDelta, ToolCallPartDelta
- `node.stream(run.ctx)` on CallToolsNode yields: FunctionToolCallEvent, FunctionToolResultEvent
- After iteration: `run.result` has the final output, `run.usage()` has token counts, `run.all_messages()` has full history

IMPORTANT: node.stream() can only be called ONCE per node (assertion error otherwise). The `async for node in run` pattern handles advancing automatically after streaming.

The target event spectrum for yielded chunks:
- {'name': 'text', 'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}
- {'name': 'tool_call', 'data': {'tool': 'name', 'args': {...}, 'call_id': '...'}, 'meta': {'stream': True, 'seq': N}}
- {'name': 'tool_result', 'data': {'tool': 'name', 'result': '...', 'call_id': '...'}, 'meta': {'stream': True, 'seq': N}}
- {'name': 'thinking', 'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}
- {'name': 'done', 'data': {'answer': '...', 'usage': {...}, 'tool_calls': N}, 'meta': {'stream': True, 'stream_end': True, 'seq': N}}

Backward compat: existing frontends that only handle 'text' and 'done' will simply ignore new event types. SSE handlers in routes_fastapi.py and network_api.py are generic pass-through — no changes needed there.

Thread pre-read and post-update logic (lines 497-589) stays exactly the same — only the core streaming loop changes.

## Instructions

Read `/workspace/packages/n3tx-agents/src/n3tx_agents/mixin.py`.

Step 1: Add new imports at the top of the file (after existing imports around line 44-56):

```python
from pydantic_ai._agent_graph import (
    ModelRequestNode, CallToolsNode, UserPromptNode, End,
)
from pydantic_ai.messages import (
    PartStartEvent, PartDeltaEvent, PartEndEvent,
    FunctionToolCallEvent, FunctionToolResultEvent,
    TextPart, ToolCallPart, ThinkingPart,
    TextPartDelta, ThinkingPartDelta, ToolCallPartDelta,
)
```

Step 2: Replace the core streaming loop in run_stream(). Find this block (approximately lines 545-613):

```python
            # Use Agent.run_stream() for token-level streaming
streamed_text = ''
async with ai_agent.call_stream(task, **run_kwargs) as result:
    async for text in result.stream_text(delta=True):
        streamed_text += text
        yield {
            # TODO Add type (tool call, thinking, response etc)
            'name': 'text',
            'data': {'text': text},
            'meta': {'stream': True, 'seq': seq},
        }
        seq += 1

    # Stream complete — emit final done chunk
    usage = result.usage()
    try:
        output = await result.get_output()
    except Exception:
        output = ''
    if not output and streamed_text:
        output = streamed_text

    all_messages = result.all_messages()

    # ── Thread: post-stream update ──
    if thread_id is not None:
        update_tx = TX(
            name='update', source=root.addr, target='threads',
            data={
                'id': thread_id,
                'messages': Thread.from_history(
                    all_messages,
                    source=root.addr,
                    target=agent_addr,
                ),
            },
            meta={'user': user} if user else {},
        )
        update_resp = await root.request(update_tx)
        if update_resp.is_error:
            logger.warning(
                "Failed to update thread %s: %s",
                thread_id,
                update_resp.data.get('message', 'unknown'),
            )

    done_data = {
        'answer': str(output),
        'usage': {
            'input_tokens': usage.input_tokens,
            'output_tokens': usage.output_tokens,
            'requests': usage.requests,
        },
    }
    if thread_id is not None:
        done_data['thread_id'] = thread_id

    # TODO
    #  Replace by returning full output (text, thinking, tool calls, any other relevant info
    #  We can probably remove streamed_text and use output.
    yield {
        'name': 'done',
        'data': done_data,
        'meta': {
            'stream': True,
            'stream_end': True,
            'seq': seq,
        },
    }
```

Replace with this new implementation using agent.iter():

```python
            # ── Rich streaming via agent.iter() graph API ──
            streamed_text = ''
            tool_call_count = 0

            async with ai_agent.iter(task, **run_kwargs) as agent_run:
                async for node in agent_run:
                    if isinstance(node, ModelRequestNode):
                        async with node.stream(agent_run.ctx) as request_stream:
                            async for event in request_stream:
                                if isinstance(event, PartStartEvent):
                                    if isinstance(event.part, ToolCallPart):
                                        tool_call_count += 1
                                        yield {
                                            'name': 'tool_call',
                                            'data': {
                                                'tool': event.part.tool_name,
                                                'args': event.part.args,
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

                # ── Iteration complete — build done chunk ──
                run_result = agent_run.result
                usage = agent_run.usage()
                output = run_result.output if run_result else ''
                if not output and streamed_text:
                    output = streamed_text
                all_messages = agent_run.all_messages()

                # ── Thread: post-stream update ──
                if thread_id is not None:
                    update_tx = TX(
                        name='update', source=root.addr, target='threads',
                        data={
                            'id': thread_id,
                            'messages': Thread.from_history(
                                all_messages,
                                source=root.addr,
                                target=agent_addr,
                            ),
                        },
                        meta={'user': user} if user else {},
                    )
                    update_resp = await root.request(update_tx)
                    if update_resp.is_error:
                        logger.warning(
                            "Failed to update thread %s: %s",
                            thread_id,
                            update_resp.data.get('message', 'unknown'),
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
                if thread_id is not None:
                    done_data['thread_id'] = thread_id

                yield {
                    'name': 'done',
                    'data': done_data,
                    'meta': {
                        'stream': True,
                        'stream_end': True,
                        'seq': seq,
                    },
                }
```

Step 3: Update the run_stream() docstring (lines 453-467) to reflect the new event types:

Find:
```python
        TX-Aligned Chunk Format:
            {'name': 'text',        'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'done',        'data': {'answer': '...', 'usage': {...}}, 'meta': {'stream_end': True}}
            {'name': 'error',       'data': {'message': '...'}, 'meta': {'error': True}}
```

Replace with:
```python
        TX-Aligned Chunk Format:
            {'name': 'text',        'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'tool_call',   'data': {'tool': '...', 'args': {...}, 'call_id': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'tool_result', 'data': {'tool': '...', 'result': '...', 'call_id': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'thinking',    'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'done',        'data': {'answer': '...', 'usage': {...}, 'tool_calls': N}, 'meta': {'stream_end': True}}
            {'name': 'error',       'data': {'message': '...'}, 'meta': {'error': True}}
```

## Conventions

Import style: `from n3tx_core.xxx import yyy`. pydantic-ai private imports (like _agent_graph) are acceptable when the public API doesn't expose what we need. Keep the same try/except error handling pattern (yield error chunk on exception). Preserve TX-aligned chunk format: every yielded dict has 'name', 'data', 'meta' keys. Use 'seq' counter for ordering. Thread pre/post patterns must match run() exactly.

## Files

**Read:** - /workspace/packages/n3tx-agents/src/n3tx_agents/mixin.py
- /workspace/packages/n3tx-agents/src/n3tx_agents/deps.py
- /workspace/packages/n3tx-agents/src/n3tx_agents/tools.py

**Modify:** - /workspace/packages/n3tx-agents/src/n3tx_agents/mixin.py

**Create:** none

## Verification

**Commands:**
- `cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py -v --tb=short -x`

**Checks:**
- run_stream() yields text chunks with name='text' (backward compat)
- run_stream() yields tool_call chunks when LLM calls tools
- run_stream() yields tool_result chunks after tool execution
- run_stream() yields done chunk with 'tool_calls' count
- run_stream() yields error chunk on failure
- Thread pre-read and post-update still work
- Existing streaming tests still pass
