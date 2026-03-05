# Agent Loop: Build Your Own vs. Use a Framework

**Research Date:** March 2026
**Context:** N3TX has an actor system (Matrix/TX message routing) with tool discovery. Currently uses pydantic-ai for the LLM agent loop. Evaluating whether to build our own.

---

## Executive Summary

> **Key Insight:** The agent loop itself is trivially simple -- 9 lines of code. The complexity is in everything around it: streaming, retries, multi-provider normalization, context window management, structured output, and keeping up with API changes every 3-6 months. The right question is not "can we build it?" but "what's the ongoing maintenance cost of owning the LLM-provider abstraction layer?"

The industry is converging on a clear pattern: **own the orchestration, delegate the LLM plumbing**. Anthropic, the 12-Factor Agents manifesto, and teams like Octomind all say the same thing -- you should own your control flow, your prompts, and your context window. But you probably should not own the HTTP client that normalizes streaming SSE chunks across three different API formats.

N3TX is already well-positioned. The current pydantic-ai integration is **thin and surgical** -- exactly 4 import sites in production code, ~80 lines of actual framework dependency. The tool routing already goes through Matrix/TX. The question is whether those 80 lines justify a dependency, or whether the hidden complexity beneath them justifies keeping it.

**Recommendation:** Keep pydantic-ai for now, but **architect for replaceability**. Extract the 3 pydantic-ai touch points behind a thin internal interface (~50 lines). This gives you the escape hatch without taking on the maintenance burden today. Revisit when/if pydantic-ai's abstractions start fighting N3TX's actor model.

---

## Table of Contents

1. [What Does a Minimal Agent Loop Actually Need?](#-what-does-a-minimal-agent-loop-actually-need)
2. [Pain Points with Frameworks (pydantic-ai, LangChain, et al.)](#-pain-points-with-frameworks)
3. [Benefits of Rolling Your Own](#-benefits-of-rolling-your-own)
4. [Hidden Complexities That Will Bite You](#%EF%B8%8F-hidden-complexities-that-will-bite-you)
5. [LLM Provider API Landscape: Converging or Diverging?](#-llm-provider-api-landscape)
6. [Multi-Provider Support Without a Framework](#-multi-provider-support-without-a-framework)
7. [Maintenance Burden of Owning the LLM Layer](#-maintenance-burden-of-owning-the-llm-layer)
8. [N3TX-Specific Analysis](#-n3tx-specific-analysis)
9. [Decision Framework](#-decision-framework)
10. [Sources](#-sources)

---

## 1. What Does a Minimal Agent Loop Actually Need?

The core insight from [Sketch.dev's "The Unreasonable Effectiveness of an LLM Agent Loop with Tool Use"](https://sketch.dev/blog/agent-loop) is that the fundamental loop is **9 lines of code**:

```python
def loop(llm):
    msg = user_input()
    while True:
        output, tool_calls = llm(msg)
        print("Agent: ", output)
        if tool_calls:
            msg = [handle_tool_call(tc) for tc in tool_calls]
        else:
            msg = user_input()
```

That is the entire agent pattern. Call the LLM, check for tool calls, execute them, feed results back. Repeat until the LLM responds with text only.

### The Minimal Components

| Component | Complexity | What It Does |
|-----------|-----------|-------------|
| **LLM API client** | Low (one provider) / High (multi-provider) | Send messages, receive completions |
| **Tool schema definition** | Low | JSON Schema describing available tools |
| **Tool call parser** | Medium | Extract tool name + args from LLM response |
| **Tool executor** | Low (you already have this) | Run the tool, return results |
| **Message history** | Medium-High | Accumulate conversation, manage token budget |
| **Loop controller** | Low | Max iterations, stop conditions |
| **Error handling** | Medium | Retry on tool failures, feed errors back to LLM |

The [12-Factor Agents](https://www.humanlayer.dev/blog/12-factor-agents) manifesto from HumanLayer codifies this further. Its core thesis: **tools are just structured outputs** -- the LLM emits JSON, your deterministic code executes it. This separation is exactly what N3TX already does via TX messages.

```
                    YOUR CODE OWNS THIS
                    =====================
[User Task] --> [Build Context] --> [LLM Call] --> [Parse Output]
                      ^                               |
                      |                    +-----------+-----------+
                      |                    |                       |
                      |              [Tool Call?]           [Text Response]
                      |                    |                       |
                      |              [Execute Tool]          [Return to User]
                      |                    |
                      +----[Feed Result]---+

                    FRAMEWORK OWNS THIS
                    ====================
                    [HTTP to LLM provider]
                    [SSE stream parsing]
                    [Token counting]
                    [Retry/backoff]
                    [Response normalization]
```

> **Key Insight:** You can build the top half of this diagram in an afternoon. The bottom half is where frameworks earn their keep -- or become a liability. The question is which half deserves your engineering time.

### What Sketch.dev Found in Practice

With just a bash tool and the 9-line loop, [Claude 3.7 Sonnet could solve many problems in "one shot"](https://sketch.dev/blog/agent-loop). But they also found that **text editing tools are "surprisingly tricky"** and agents sometimes produce counterproductive solutions (skipping failing tests rather than fixing them). The loop is simple; the tools and prompts are where the real engineering happens.

---

## 2. Pain Points with Frameworks

### LangChain: The Cautionary Tale

[Octomind used LangChain in production for 12+ months](https://www.octomind.dev/blog/why-we-no-longer-use-langchain-for-building-our-ai-agents) (early 2023 through 2024) before removing it entirely. Their experience is representative of the broader industry sentiment:

| Pain Point | Detail |
|-----------|--------|
| **Rigid abstractions** | "LangChain tries to make your life easier by doing more with less code by hiding details away from you. But when this comes at the cost of simplicity and flexibility, abstractions lose their value." |
| **Debugging overhead** | Team spent "as much time understanding and debugging LangChain as it did building features" |
| **Inflexibility** | Couldn't spawn sub-agents, observe agent state externally, or change tool availability based on business logic |
| **Breaking changes** | Rapid development pace led to frequent API breaks without clear communication |
| **Performance** | Engineers cut API latency by **>1 second** just by removing LangChain's memory wrapper ([source](https://www.designveloper.com/blog/is-langchain-bad/)) |

The numbers are damning. According to the [2025 AI Developer Survey](https://medium.com/@greekofai/why-45-of-developers-never-use-langchain-in-production-the-shocking-reality-behind-ais-most-145265efe17b): **45% of developers who experiment with LangChain never use it in production**, and **23% who initially adopted it eventually removed it entirely**.

Octomind replaced LangChain with **direct LLM client libraries + modular packages** for specific functions. Their development speed increased, team friction decreased, and they "no longer had to translate requirements into LangChain-appropriate solutions."

### Pydantic-AI: The Lighter-Weight Option

Pydantic-AI is a fundamentally different beast than LangChain. It reached [V1 in September 2025](https://pydantic.dev/articles/pydantic-ai-v1), committing to API stability until V2. Its design philosophy is closer to FastAPI than LangChain -- type-safe, minimal abstractions, good DX.

**What it provides well:**

- Built-in agent loop with tool calling
- Type-safe tool definitions via Python type hints
- `Agent.iter()` for [low-level control over the agent loop](https://ai.pydantic.dev/agent/) -- you can step through nodes manually
- OpenTelemetry instrumentation out of the box
- [Streamed structured output with validation](https://ai.pydantic.dev/)
- Human-in-the-loop tool approval
- Multi-provider support (OpenAI, Anthropic, Google, Ollama, etc.)

**Reported pain points:**

| Issue | Severity for N3TX |
|-------|-------------------|
| Context window bloat with many tools | **Medium** -- N3TX tool count is bounded by registered models |
| Agent coordination complexity | **Low** -- N3TX handles coordination via Matrix/TX, not pydantic-ai |
| Output validation inconsistencies in production | **Low** -- N3TX uses schema-driven validation already |
| Emerging ecosystem (skills/plugins still maturing) | **Low** -- N3TX doesn't use the plugin ecosystem |
| Framework opinions vs. your opinions | **Watch** -- could become friction as N3TX's agent model matures |

[Martin Fowler's team built a CLI coding agent with pydantic-ai](https://martinfowler.com/articles/build-own-coding-agent.html) and found the "how little code this is" was a key advantage. They highlighted MCP integration as particularly valuable. But their use case (coding agent) is different from N3TX's (schema-driven CRUD agents).

### Framework Comparison Summary

| Dimension | LangChain | Pydantic-AI | Custom Loop |
|-----------|----------|-------------|-------------|
| **Learning curve** | Steep | Moderate | Low (you wrote it) |
| **Abstraction level** | High (opaque) | Medium (inspectable) | None (you own it) |
| **Multi-provider** | Yes (100+) | Yes (10+) | DIY |
| **Debugging** | Hard (deep stack traces) | Good (thin layer) | Best (your code) |
| **Breaking changes** | Frequent (historically) | Stable post-V1 | You control it |
| **Streaming** | Built-in | Built-in | DIY per provider |
| **Type safety** | Limited | Strong | DIY |
| **Community/ecosystem** | Large | Growing | Just you |

---

## 3. Benefits of Rolling Your Own

### The "Most Strong Founders" Data Point

From the [12-Factor Agents](https://www.humanlayer.dev/blog/12-factor-agents) research, after talking to "at least 100 SaaS builders":

> "Most strong technical founders are rolling the stack themselves. Few frameworks are visible in production customer-facing agents."

The 12 factors distill what these teams learned:

1. **Natural Language to Tool Calls** -- LLM outputs JSON, code executes it
2. **Own Your Prompts** -- "Don't outsource prompt engineering to a framework"
3. **Own Your Context Window** -- Custom formats (XML, YAML) can be more efficient than message arrays
4. **Tools Are Just Structured Outputs** -- The LLM emits intent, you decide what to do with it
5. **Unify Execution State and Business State** -- One thread, one state
6. **Launch/Pause/Resume with Simple APIs** -- Durability primitives
7. **Contact Humans with Tool Calls** -- Human approval as a tool
8. **Own Your Control Flow** -- Intercept, pause, rate-limit, escalate
9. **Compact Errors into Context** -- Feed errors back, set retry limits
10. **Small, Focused Agents** -- 3-20 steps max
11. **Trigger from Anywhere** -- Events, webhooks, crons
12. **Make Your Agent a Stateless Reducer** -- Input + logic = output

> **Key Insight:** Factors 1, 3, 4, 8, and 12 argue strongly for owning the loop. But none of them argue for owning the HTTP client to the LLM provider. The 12-Factor philosophy is about owning **orchestration**, not **plumbing**.

### What Anthropic Says

[Anthropic's "Building Effective Agents" guide](https://www.anthropic.com/research/building-effective-agents) is emphatic:

> "Start by using LLM APIs directly: many patterns can be implemented in a few lines of code. Frameworks often create extra layers of abstraction that can obscure the underlying prompts and responses, making them harder to debug."

They distinguish between **workflows** (predefined code paths with LLM steps) and **agents** (LLM dynamically directs its own process). Most production systems are workflows, not agents. The complexity ladder goes:

```
Simplest ──────────────────────────────────────────── Most Complex

[Single LLM Call] → [Prompt Chain] → [Router] → [Parallel] → [Orchestrator-Worker] → [Agent Loop]
                                                                                          ^
                                                                               You are here
```

Their core advice: **add complexity only when it demonstrably improves measurable outcomes**.

### The Inngest "Harness, Not Framework" Argument

[Inngest's blog post](https://www.inngest.com/blog/your-agent-needs-a-harness-not-a-framework) makes a subtle distinction:

> "Every agent framework is building one from scratch -- their own retry logic, their own state persistence, their own job queues, their own event routing."

Their argument: **you don't need an agent framework; you need durable infrastructure** (retry, state, events) wrapped around a simple loop. This maps remarkably well to N3TX's architecture -- Matrix is already an event router, TX is already a message envelope, interceptors already provide middleware.

---

## 4. Hidden Complexities That Will Bite You

The 9-line loop is a lie. A production agent loop needs to handle a long tail of problems that frameworks absorb. Here is where the real engineering cost lives:

### 4.1 Streaming

Each provider implements SSE streaming differently:

| Aspect | OpenAI | Anthropic | Google |
|--------|--------|-----------|--------|
| **Event format** | `data:` lines only | `event:` + `data:` lines | Server-sent events with consistent structure |
| **Token usage** | Last chunk only | Input tokens in first chunk, output in last | Built into response structure |
| **Tool calls in stream** | Delta-based accumulation | Mixed with content blocks | Different structure entirely |
| **Stream termination** | `data: [DONE]` | `message_stop` event | Connection close |

If you need streaming (and for any user-facing agent, you do), you need **per-provider stream parsers**. This is not trivial code -- it is fragile, edge-case-heavy, and changes when providers update their APIs.

### 4.2 Context Window Management

[Anthropic's context engineering guide](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (September 2025) defines this as "the art and science of curating what will go into the limited context window":

- **Context rot**: as token count increases, recall accuracy **decreases**
- **Threshold**: summarize or truncate when token count exceeds **50% of context window**
- **Compaction**: summarize conversation, reinitiate with summary
- **Tool result clearing**: lightweight compaction -- trim bloated tool outputs
- **Sub-agent architecture**: specialized agents return condensed summaries (1,000-2,000 tokens)

[Inngest's Utah project](https://www.inngest.com/blog/your-agent-needs-a-harness-not-a-framework) implemented tiered solutions:
- Soft-trimming tool results: keep head/tail at **1,500 chars each**
- Hard-clearing beyond **50,000 character threshold**
- Conversation compaction when tokens exceed limits
- Budget warnings at iteration limits

### 4.3 Retries, Rate Limits, and Infinite Loops

> **Warning:** [One company's multi-agent system escalated from $127/week to $47,000 over four weeks](https://www.zenml.io/blog/the-agent-deployment-gap-why-your-llm-loop-isnt-production-ready-and-what-to-do-about-it) due to an infinite conversation loop between agents running undetected for 11 days.

[Toqan's data analyst agent](https://www.zenml.io/blog/the-agent-deployment-gap-why-your-llm-loop-isnt-production-ready-and-what-to-do-about-it) experienced "infinite loops where agents ignored stop commands, repetitive responses (giving the same answer 58-59 times), and inconsistent behavior across runs."

You need:
- **Max iteration limits** (pydantic-ai provides `UsageLimits`)
- **Token budget caps** (per-run and per-period)
- **Exponential backoff** for rate limits (varies by provider)
- **Circuit breakers** for runaway agents
- **Cost tracking** per request

### 4.4 Structured Output / Tool Call Parsing

OpenAI supports `strict: true` for [guaranteed JSON Schema conformance](https://developers.openai.com/api/docs/guides/structured-outputs/). Anthropic and Google have their own mechanisms. The format of tool calls in responses differs:

```
OpenAI:    response.choices[0].message.tool_calls[i].function.{name, arguments}
Anthropic: response.content[i].type == "tool_use" → .name, .input
Google:    response.candidates[0].content.parts[i].function_call.{name, args}
```

Each one returns arguments in slightly different JSON shapes. Parsing, validating, and routing these requires per-provider logic.

### 4.5 Token Counting

You cannot manage context windows without counting tokens. But token counting is model-specific:
- OpenAI: `tiktoken` library, different encodings per model family
- Anthropic: API returns counts, but pre-request estimation requires their tokenizer
- Google: `count_tokens` API endpoint

### 4.6 Production Complexity Scorecard

| Challenge | Effort to Build | Effort to Maintain | Framework Handles It? |
|-----------|----------------|-------------------|---------------------|
| Basic loop | 1 day | Negligible | Yes |
| Single-provider API client | 2-3 days | Low | Yes |
| Multi-provider normalization | 1-2 weeks | **High** (API changes every 3-6 months) | Yes |
| Streaming (single provider) | 2-3 days | Medium | Yes |
| Streaming (multi-provider) | 1-2 weeks | **High** | Yes |
| Context window management | 1 week | Medium | Partially |
| Token counting | 2-3 days | Medium | Yes |
| Structured output validation | 3-5 days | Medium | Yes |
| Retry/backoff/rate limiting | 2-3 days | Low | Yes |
| Cost tracking | 1-2 days | Medium (pricing changes) | Partially |
| **Total** | **5-8 weeks** | **~1 engineer-week/quarter** | -- |

---

## 5. LLM Provider API Landscape

### Not Converging -- Fragmenting

The three major providers are **diverging**, not converging:

- **OpenAI** released the [Responses API](https://platform.openai.com/docs/guides/migrate-to-responses) in March 2025 as a replacement for Chat Completions. It uses "Items" instead of "Messages" and includes built-in tools (web search, file search, computer use). Internal evals show **3% improvement on SWE-bench** and **40-80% better cache utilization** vs. Chat Completions.

- **Anthropic** uses the Messages API with content blocks. Tool calls are [mixed into content blocks](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) alongside text. They introduced [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) with `cache_control` markers and ephemeral TTLs (5 min default, 1 hour at extra cost). Cache reads cost **0.1x base input price**.

- **Google** uses the `generateContent` format. Different structure entirely. Pushing its own A2A (Agent-to-Agent) protocol.

Each provider is also pushing their own ecosystem play:
- OpenAI: Responses API + Agents SDK
- Anthropic: MCP (Model Context Protocol)
- Google: ADK (Agent Development Kit) + A2A

```
           OpenAI                    Anthropic                 Google
    ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
    │ Responses API    │     │ Messages API     │     │ generateContent  │
    │ (Items, not Msgs)│     │ (Content Blocks) │     │ (Parts-based)    │
    ├──────────────────┤     ├──────────────────┤     ├──────────────────┤
    │ tool_calls in    │     │ tool_use blocks  │     │ function_call in │
    │ response.output  │     │ in content[]     │     │ parts[]          │
    ├──────────────────┤     ├──────────────────┤     ├──────────────────┤
    │ Agents SDK       │     │ MCP              │     │ ADK + A2A        │
    └──────────────────┘     └──────────────────┘     └──────────────────┘
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       │
                        ┌──────────────────────────┐
                        │   YOUR NORMALIZATION     │
                        │   LAYER (or framework)   │
                        └──────────────────────────┘
```

### The "OpenAI-Compatible" Myth

Many open-source providers (Ollama, vLLM, Together AI, Groq) offer OpenAI-compatible endpoints. But "compatible" means **chat completions compatible** -- not Responses API compatible. The gap is widening. And Anthropic and Google have never offered OpenAI-compatible endpoints natively.

The market response has been **gateway layers** like LiteLLM (100+ providers, OpenAI-compatible interface). But [LiteLLM has production issues at scale](https://dev.to/debmckinney/top-5-litellm-alternatives-in-2025-1pki): performance degradation, memory leaks, and latency overhead that "becomes a bottleneck for real-time applications."

---

## 6. Multi-Provider Support Without a Framework

Teams that go framework-free for multi-provider support typically adopt one of these patterns:

### Pattern 1: Gateway Proxy (LiteLLM / Portkey / Bifrost)

```
[Your Code] --OpenAI format--> [Gateway] --native format--> [Provider]
```

- **Pro**: One API format in your code
- **Con**: Additional network hop, [latency overhead](https://dev.to/debmckinney/top-5-litellm-alternatives-in-2025-1pki), another system to maintain/monitor
- **Con**: Gateway must keep up with provider changes (LiteLLM has [9,000+ GitHub issues](https://github.com/BerriAI/litellm))

### Pattern 2: Thin Adapter Layer (DIY)

```python
class LLMProvider(Protocol):
    async def complete(self, messages: list, tools: list) -> LLMResponse: ...
    async def stream(self, messages: list, tools: list) -> AsyncIterator[LLMChunk]: ...

class OpenAIProvider(LLMProvider): ...
class AnthropicProvider(LLMProvider): ...
class OllamaProvider(LLMProvider): ...
```

- **Pro**: Full control, no gateway dependency
- **Con**: You maintain per-provider adapters. **API changes every 3-6 months** ([source](https://markaicode.com/future-proofing-llm-applications-model-updates/)). 67% of LLM applications [experience service disruptions during major model updates](https://markaicode.com/future-proofing-llm-applications-model-updates/).
- **Con**: Streaming normalization is the hard part -- not the happy path

### Pattern 3: Use a Framework for Provider Abstraction Only

This is effectively what N3TX does with pydantic-ai. Use the framework's `Agent` + model routing, but own everything else (tool discovery, execution, context management, orchestration).

- **Pro**: Provider changes are someone else's problem
- **Con**: Framework still has opinions about tool calling, message format, etc.
- **Con**: Version updates can still break your integration

### Provider Adapter Maintenance Reality

According to [Gartner research cited by ProxAI](https://www.proxai.co/blog/archive/llm-abstraction-layer), the lack of standardized LLM interoperability costs enterprises **$2.7 billion annually** in wasted engineering time. Even for a small team, the maintenance is real:

| Provider Event | Frequency | Your Effort (DIY) |
|---------------|-----------|-------------------|
| New model release | Monthly | Test compatibility, update defaults |
| API parameter changes | Quarterly | Update adapter code |
| New API version (e.g., Responses API) | Annually | Major refactor of adapter |
| Model deprecation | Every 6 months | Migration, testing |
| Pricing changes | Monthly | Update cost tracking |
| New capability (e.g., prompt caching) | Quarterly | New adapter code to leverage |

---

## 7. Maintenance Burden of Owning the LLM Layer

### The Two-Layer Analysis

Think of the LLM integration as two distinct layers:

```
┌─────────────────────────────────────────────────┐
│  ORCHESTRATION LAYER  (own this)                │
│  ── Agent loop control flow                     │
│  ── Tool discovery & execution                  │
│  ── Context window management                   │
│  ── State persistence                           │
│  ── Auth / access control                       │
│  ── Cost tracking & limits                      │
│  ── Observability / logging                     │
│                                                 │
│  This is YOUR competitive advantage.            │
│  N3TX already owns most of this via Matrix/TX.  │
├─────────────────────────────────────────────────┤
│  PROVIDER LAYER  (delegate this)                │
│  ── HTTP client to LLM API                      │
│  ── SSE stream parsing                          │
│  ── Response normalization                      │
│  ── Token counting                              │
│  ── Retry / rate limiting                       │
│  ── Multi-provider routing                      │
│  ── Structured output enforcement               │
│                                                 │
│  This is COMMODITY PLUMBING.                    │
│  Maintaining it is pure cost, zero advantage.   │
└─────────────────────────────────────────────────┘
```

> **Key Insight:** The orchestration layer is where N3TX's actor system provides genuine differentiation. The provider layer is undifferentiated toil. The ideal architecture owns the top and delegates the bottom.

### What Other Teams Report

**Teams that built their own** (from [Hacker News discussions](https://news.ycombinator.com/item?id=43998472) and the [12-Factor Agents community](https://github.com/humanlayer/12-factor-agents)):

- "Building the loop took a day. Maintaining provider adapters is the ongoing tax."
- Teams using only one provider (Anthropic OR OpenAI) report low maintenance burden
- Teams supporting 2+ providers report "it's a part-time job keeping adapters current"
- Most "built our own" teams use LiteLLM or similar for the provider layer anyway

**Teams that kept a framework:**

- [Martin Fowler's team](https://martinfowler.com/articles/build-own-coding-agent.html) found pydantic-ai's MCP integration and minimal code requirements valuable enough to justify the dependency
- Teams using pydantic-ai's `Agent.iter()` report good low-level control without losing provider abstraction
- The main complaint: framework opinions about message format and tool calling can conflict with custom needs

### The "Dependency Weight" of Pydantic-AI

Pydantic-AI is notably lighter than LangChain:

| Metric | LangChain | Pydantic-AI |
|--------|----------|-------------|
| PyPI dependencies | 15+ direct, 50+ transitive | ~5 direct (pydantic, httpx, etc.) |
| API surface | Enormous (chains, agents, memory, callbacks, ...) | Small (Agent, Tool, RunContext) |
| Breaking changes (2024-2025) | Frequent | Stable post-V1 (Sep 2025) |
| Abstraction depth | 5-10 layers deep | 2-3 layers |
| "Debug time" | Often exceeds feature time ([Octomind](https://www.octomind.dev/blog/why-we-no-longer-use-langchain-for-building-our-ai-agents)) | Comparable to direct API use |
| Provider support | 100+ | 10+ major providers |

---

## 8. N3TX-Specific Analysis

### Current Pydantic-AI Integration Surface

The current integration is remarkably thin. Here is **every production-code touch point**:

| File | Import | What It Uses |
|------|--------|-------------|
| `agents/mixin.py` (line 63) | `from pydantic_ai import Agent, UsageLimits` | Creates Agent, sets iteration limits |
| `agents/tools.py` (line 195) | `from pydantic_ai import ModelRetry` | Raises retry on tool error |
| `agents/tools.py` (line 276) | `from pydantic_ai.tools import Tool` | Wraps tool functions |
| `agents/deps.py` | `AgentDeps` dataclass | Passed as `deps_type` to Agent |

**Total framework-coupled code: ~30 lines** (the `agent_run()` method in `mixin.py` lines 63-140).

Everything else -- tool discovery, tool execution routing, TX message creation, adapter management, auth context injection -- is **pure N3TX code** that talks to Matrix.

```
┌──────────────────────────────────────────────────────────┐
│  agent_run()  in  mixin.py                               │
│                                                          │
│  ┌──── N3TX Code ────────────────────────────────────┐   │
│  │  Tool discovery (discover_tools)                  │   │
│  │  Adapter creation (NetworkAdapter)                │   │
│  │  TX message routing (_route_tool_call)             │   │
│  │  Auth context (AgentDeps)                         │   │
│  │  Cleanup (adapter removal)                        │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──── Pydantic-AI Code ─────────────────────────────┐   │
│  │  Agent(llm, system_prompt, tools, deps_type)      │   │
│  │  result = await agent.run(task, deps, limits)     │   │
│  │  result.output / result.usage() / result.messages │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### What Pydantic-AI Actually Does for N3TX

Behind those 30 lines, pydantic-ai handles:

1. **The LLM API call** (HTTP, auth, retries)
2. **Tool call detection** in the response
3. **Tool call execution** (calling the wrapper functions that N3TX provides)
4. **Looping** until no more tool calls
5. **Token counting** and usage tracking
6. **Model routing** (parsing `"anthropic:claude-sonnet-4-5-20250929"` into the right API client)
7. **Response normalization** across providers
8. **Structured output** validation (if used)

### What N3TX Would Need to Replace It

To drop pydantic-ai, N3TX would need to implement:

```python
# Minimal replacement (single provider, no streaming)
class AgentLoop:
    def __init__(self, llm_client, system_prompt, tools):
        self.client = llm_client
        self.prompt = system_prompt
        self.tools = tools  # JSON Schema definitions

    async def run(self, task, deps, max_iterations=10):
        messages = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": task},
        ]

        for i in range(max_iterations):
            response = await self.client.complete(messages, self.tools)

            if not response.tool_calls:
                return AgentResult(
                    output=response.text,
                    usage=response.usage,
                    messages=messages,
                )

            # Execute tool calls
            for tc in response.tool_calls:
                result = await deps.execute_tool(tc.name, tc.args)
                messages.append({"role": "tool", "content": result, "tool_call_id": tc.id})

            messages.append(response.as_message())

        raise MaxIterationsExceeded(max_iterations)
```

This is ~30 lines -- roughly the same as the current pydantic-ai integration. **But** it assumes a single `llm_client` that already handles:
- HTTP to the provider
- Response parsing
- Error handling
- Token counting

For a single provider (Anthropic via `anthropic` SDK), this is practical. For multi-provider support, you either need per-provider adapters or a gateway.

### The N3TX Advantage: Tool Routing Already Exists

The most valuable thing frameworks typically provide -- tool execution with proper typing -- is something N3TX already solves better than any framework could:

```
[LLM says "call grants_create(name='...')"]
    │
    ├── Framework approach: call a Python function registered with the framework
    │
    └── N3TX approach: create TX(name='create', target='grants', data={...})
                       route through Matrix
                       interceptors run (auth, logging, rate limiting)
                       handler_crud() processes it
                       response TX comes back

        THIS IS BETTER. You get auth, interceptors, and the full actor
        lifecycle for free. No framework provides this.
```

---

## 9. Decision Framework

### The Three Options

| Option | Description | Effort | Risk |
|--------|------------|--------|------|
| **A: Keep pydantic-ai** | Current state. 30 lines of dependency. | Zero | Framework diverges from N3TX needs |
| **B: Abstract behind interface** | Thin N3TX interface over pydantic-ai. Swap later if needed. | 1-2 days | Minor over-engineering |
| **C: Full replacement** | Build custom loop + provider adapters. | 3-8 weeks | Ongoing maintenance of provider layer |

### Decision Matrix

| Factor | Option A (Keep) | Option B (Abstract) | Option C (Replace) |
|--------|----------------|--------------------|--------------------|
| Immediate effort | None | 1-2 days | 3-8 weeks |
| Ongoing maintenance | Pydantic-AI updates | Minimal | ~1 engineer-week/quarter |
| Multi-provider | Free | Free | DIY or add LiteLLM |
| Streaming (future) | Free | Free | 1-2 weeks per provider |
| Debugging | Good | Good | Best |
| Framework lock-in risk | Low (thin surface) | Very low | None |
| Alignment with 12-Factor | Good enough | Better | Best (in theory) |
| Token counting | Free | Free | DIY |

### Recommended Path: Option B (Abstract Behind Interface)

```python
# n3tx/core/agents/llm.py  (~50 lines)

from dataclasses import dataclass
from typing import Protocol, Any

@dataclass
class LLMResult:
    output: str
    usage: dict  # {input_tokens, output_tokens, requests}
    messages: int

class LLMEngine(Protocol):
    """Interface for swappable LLM backends."""
    async def run(
        self,
        prompt: str,
        task: str,
        tools: list,  # pydantic-ai Tool objects or ToolSpecs
        deps: Any,
        max_iterations: int | None = None,
    ) -> LLMResult: ...

class PydanticAIEngine:
    """Default implementation using pydantic-ai."""
    def __init__(self, llm: str):
        self.llm = llm

    async def run(self, prompt, task, tools, deps, max_iterations=None):
        from pydantic_ai import Agent, UsageLimits
        agent = Agent(self.llm, system_prompt=prompt, tools=tools, deps_type=type(deps))
        limits = UsageLimits(request_limit=max_iterations) if max_iterations else None
        result = await agent.run(task, deps=deps, usage_limits=limits)
        usage = result.usage()
        return LLMResult(
            output=result.output,
            usage={'input_tokens': usage.input_tokens, 'output_tokens': usage.output_tokens, 'requests': usage.requests},
            messages=len(result.all_messages()),
        )
```

This gives you:
- **Today**: zero behavior change, pydantic-ai does the work
- **Tomorrow**: swap `PydanticAIEngine` for `DirectAnthropicEngine` if pydantic-ai becomes a problem
- **Never**: you don't have to build multi-provider support until you need it

> **Key Insight:** The best time to build your own agent loop is when pydantic-ai actively fights you. Not before. The current integration surface is so thin (30 lines) that extracting it later is trivial. An abstraction interface adds ~50 lines of code and makes that extraction a 1-hour job instead of a 1-day job.

### When to Revisit This Decision

Pull the trigger on Option C (full replacement) if any of these become true:

- Pydantic-AI introduces abstractions that conflict with TX-based tool routing
- You need streaming and pydantic-ai's streaming model doesn't fit N3TX's SSE patterns
- You go single-provider (Anthropic only) and the `anthropic` SDK alone covers your needs
- Pydantic-AI's dependency chain creates conflicts with N3TX's dependencies
- The framework's update cadence creates more work than writing your own loop would

---

## Appendix: What the Industry Leaders Say

### Anthropic (December 2024)

> "The most successful implementations use **simple, composable patterns** rather than complex frameworks... add complexity only when it demonstrably improves outcomes."

([Building Effective AI Agents](https://www.anthropic.com/research/building-effective-agents))

### Dex Horthy, HumanLayer (2025)

> "Getting past 80% requires reverse-engineering the framework, prompts, flow, etc... Most 'AI agents' that succeed in production aren't magical autonomous beings -- they're mostly **well-engineered traditional software**, with LLM capabilities carefully sprinkled in."

([12-Factor Agents](https://www.humanlayer.dev/blog/12-factor-agents))

### Octomind Engineering (2024)

> "We spent as much time understanding and debugging LangChain as we did building features... We replaced LangChain's rigid high-level abstractions with **modular building blocks**, which simplified our codebase and made our team happier."

([Why We No Longer Use LangChain](https://www.octomind.dev/blog/why-we-no-longer-use-langchain-for-building-our-ai-agents))

### Phil Rosenberg, Sketch.dev (2025)

> "The main loop of using an LLM with tool use is unreasonably effective and surprisingly simple... agent loops will likely be incorporated into more day-to-day automation tasks."

([The Unreasonable Effectiveness of an LLM Agent Loop](https://sketch.dev/blog/agent-loop))

### Inngest Engineering (2025)

> "Agent runtimes don't need yet another framework -- they need a **durable, event-driven harness** that connects tools, memory, and models on production-grade infrastructure."

([Your Agent Needs a Harness, Not a Framework](https://www.inngest.com/blog/your-agent-needs-a-harness-not-a-framework))

### Simon Willison (2025)

> "An LLM agent is something that runs tools in a loop to achieve a goal... Designing agentic loops is a very new skill."

([Designing Agentic Loops](https://simonwillison.net/2025/Sep/30/designing-agentic-loops/))

---

## Appendix: Build-vs-Buy Case Studies

| Company | Initial Choice | What Happened | Outcome |
|---------|---------------|---------------|---------|
| **Octomind** | LangChain (12+ months) | Rigid abstractions, debugging overhead, couldn't observe agent state | Replaced with direct LLM clients + modular packages. Dev speed increased. |
| **Toqan** | Custom build | Infinite loops, 58-59x repeated responses, inconsistent behavior | Added PostgreSQL state management, Redis caching, explicit loop guards |
| **Parcha** | Custom build | WebSocket disconnections mid-conversation, no recovery | Architectural redesign for resumability |
| **Martin Fowler's team** | Pydantic-AI | "How little code this is" -- worked well for coding agent | Kept pydantic-ai, valued MCP integration |
| **Minimal AI** | LangGraph + LangSmith | Multi-agent customer support system | 80%+ efficiency gains, kept LangGraph for orchestration |
| **Sketch.dev** | Custom (9-line loop) | Works "unreasonably well" with Claude + bash tool | Kept custom, added a handful of extra tools for quality |
| **Inngest** | Custom (Utah harness) | Built durable event-driven harness around simple loop | Context management was hardest part, not LLM integration |
| **Unknown company** (via ZenML) | Multi-agent custom | Agents in infinite conversation loop for 11 days | Cost escalated from $127/week to **$47,000 over 4 weeks** |

---

## 🔗 Sources

1. [The Unreasonable Effectiveness of an LLM Agent Loop with Tool Use](https://sketch.dev/blog/agent-loop) -- Sketch.dev, May 2025
2. [Why We No Longer Use LangChain for Building Our AI Agents](https://www.octomind.dev/blog/why-we-no-longer-use-langchain-for-building-our-ai-agents) -- Octomind, 2024
3. [12-Factor Agents: Patterns of Reliable LLM Applications](https://www.humanlayer.dev/blog/12-factor-agents) -- HumanLayer/Dex Horthy, 2025
4. [Building Effective AI Agents](https://www.anthropic.com/research/building-effective-agents) -- Anthropic, December 2024
5. [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) -- Anthropic Engineering, September 2025
6. [Your Agent Needs a Harness, Not a Framework](https://www.inngest.com/blog/your-agent-needs-a-harness-not-a-framework) -- Inngest Blog, 2025
7. [Building Your Own CLI Coding Agent with Pydantic-AI](https://martinfowler.com/articles/build-own-coding-agent.html) -- Martin Fowler, 2025
8. [The Agent Deployment Gap: Why Your LLM Loop Isn't Production-Ready](https://www.zenml.io/blog/the-agent-deployment-gap-why-your-llm-loop-isnt-production-ready-and-what-to-do-about-it) -- ZenML Blog, 2025
9. [Comparing Open-Source AI Agent Frameworks](https://langfuse.com/blog/2025-03-19-ai-agent-comparison) -- Langfuse Blog, March 2025
10. [Designing Agentic Loops](https://simonwillison.net/2025/Sep/30/designing-agentic-loops/) -- Simon Willison, September 2025
11. [Migrate to the Responses API](https://platform.openai.com/docs/guides/migrate-to-responses) -- OpenAI Documentation, 2025
12. [Pydantic AI Documentation](https://ai.pydantic.dev/) -- Pydantic, 2025-2026
13. [Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) -- Anthropic Claude API Docs
14. [LangChain vs PydanticAI for Building an AI Agent](https://medium.com/@finndersen/langchain-vs-pydanticai-for-building-an-ai-agent-e0a059435e9d) -- Finn Andersen, Medium
15. [Why 45% of Developers Never Use LangChain in Production](https://medium.com/@greekofai/why-45-of-developers-never-use-langchain-in-production-the-shocking-reality-behind-ais-most-145265efe17b) -- Greek AI, Medium
16. [Top 5 LiteLLM Alternatives in 2025](https://dev.to/debmckinney/top-5-litellm-alternatives-in-2025-1pki) -- DEV Community
17. [LLM Abstraction Layer: Why Your Codebase Needs One](https://www.proxai.co/blog/archive/llm-abstraction-layer) -- ProxAI, 2025
18. [Future-Proofing LLM Applications](https://markaicode.com/future-proofing-llm-applications-model-updates/) -- MarkAICode
19. [14 AI Agent Frameworks Compared](https://softcery.com/lab/top-14-ai-agent-frameworks-of-2025-a-founders-guide-to-building-smarter-systems) -- Softcery, 2025
20. [State of AI Agents](https://www.langchain.com/state-of-agent-engineering) -- LangChain, 2025
21. [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs/) -- OpenAI API Docs
22. [Comparing Streaming Response Structures for Different LLM APIs](https://medium.com/percolation-labs/comparing-the-streaming-response-structure-for-different-llm-apis-2b8645028b41) -- Percolation Labs, Medium
