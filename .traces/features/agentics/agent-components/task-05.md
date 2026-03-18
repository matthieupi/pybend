# Enhance ntx-chat.js to render typed stream events

**ID:** task-05 | **Wave:** 3 | **Depends on:** task-01

## Intent

The chat component currently treats all stream chunks as text. With the new typed events from run_stream(), the chat should visually distinguish tool calls (collapsible cards), tool results (appended to their tool card), and thinking tokens (subtle indicator), giving users visibility into agent reasoning.

## Context

ntx-chat.js lives at packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js. The _sendStream() method (lines 130-171) handles SSE chunks. Currently it uses a single code path for all chunks (line 148): `const t = chunk.data?.text || chunk.text || chunk.chunk || chunk.content || ''`.

The component is a standalone Web Component with shadow DOM, no external CSS dependencies. It uses HTTP.stream() for SSE with three callbacks: onChunk, onDone, onError.

The new typed events to handle:
- tool_call: {name: 'tool_call', data: {tool, args, call_id}}
- tool_result: {name: 'tool_result', data: {tool, result, call_id}}
- thinking: {name: 'thinking', data: {text}}
- text: {name: 'text', data: {text}} — unchanged
- done: {name: 'done', data: {answer, usage, tool_calls}} — unchanged

Design:
- tool_call: compact inline card in chat flow showing tool name + spinning indicator
- tool_result: result summary appended under matching tool_call card (matched by call_id)
- thinking: subtle animated dots or italic text, collapsed when done
- text: unchanged progressive text append
- done: unchanged cleanup

## Instructions

Read `/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`.

Step 1: Replace the _sendStream() method (lines 130-171) with a version that dispatches on chunk.name:

Find the entire _sendStream method and replace with:
```javascript
    _sendStream(url, payload) {
        this._isStreaming = true;
        this._els.send.disabled = true;
        let text = '';
        const msgEl = this._appendMsg('assistant', '');
        const textEl = msgEl.querySelector('.msg-text');
        this._toolCards = new Map(); // call_id → DOM element

        this._streamHandle = HTTP.stream(url, payload,
            (chunk) => {
                switch (chunk.name) {
                    case 'thinking': {
                        let thinkEl = msgEl.querySelector('.msg-thinking');
                        if (!thinkEl) {
                            thinkEl = document.createElement('div');
                            thinkEl.className = 'msg-thinking';
                            thinkEl.innerHTML = '<span class="thinking-dots">thinking</span>';
                            msgEl.insertBefore(thinkEl, textEl);
                        }
                        break;
                    }
                    case 'tool_call': {
                        // Remove thinking indicator when tools start
                        msgEl.querySelector('.msg-thinking')?.remove();
                        const card = document.createElement('div');
                        card.className = 'tool-card';
                        card.innerHTML = `<div class="tool-header"><span class="tool-icon">\u2699</span> ${this._esc(chunk.data.tool)} <span class="tool-spin">\u25CF</span></div>`;
                        msgEl.insertBefore(card, textEl);
                        if (chunk.data.call_id) this._toolCards.set(chunk.data.call_id, card);
                        break;
                    }
                    case 'tool_result': {
                        const card = chunk.data.call_id && this._toolCards.get(chunk.data.call_id);
                        if (card) {
                            card.querySelector('.tool-spin')?.remove();
                            const summary = (chunk.data.result || '').slice(0, 120);
                            card.innerHTML += `<div class="tool-result">${this._esc(summary)}</div>`;
                        }
                        break;
                    }
                    case 'done': {
                        msgEl.querySelector('.msg-thinking')?.remove();
                        if (chunk.data?.answer && !text) {
                            textEl.textContent = chunk.data.answer;
                            text = chunk.data.answer;
                        }
                        // Show usage stats if available
                        if (chunk.data?.tool_calls > 0) {
                            const stats = document.createElement('div');
                            stats.className = 'msg-stats';
                            stats.textContent = `${chunk.data.tool_calls} tool call${chunk.data.tool_calls > 1 ? 's' : ''}`;
                            msgEl.appendChild(stats);
                        }
                        break;
                    }
                    default: {
                        // 'text' and any unknown types — progressive text append
                        msgEl.querySelector('.msg-thinking')?.remove();
                        const t = chunk.data?.text || chunk.text || chunk.chunk || chunk.content || '';
                        text += t;
                        textEl.textContent = text;
                        msgEl.querySelector('.cursor')?.remove();
                        textEl.insertAdjacentHTML('afterend', '<span class="cursor">|</span>');
                    }
                }
                this._scrollToBottom();
            },
            (data) => {
                this._isStreaming = false;
                this._streamHandle = null;
                this._els.send.disabled = false;
                this._toolCards = null;
                msgEl.querySelector('.cursor')?.remove();
                msgEl.querySelector('.msg-thinking')?.remove();
                this._scrollToBottom();
            },
            (err) => {
                this._isStreaming = false;
                this._streamHandle = null;
                this._els.send.disabled = false;
                this._toolCards = null;
                msgEl.querySelector('.cursor')?.remove();
                msgEl.querySelector('.msg-thinking')?.remove();
                this._appendMsg('system', `Error: ${err?.message || err?.detail || err}`);
            },
        );
    }
```

Step 2: Add CSS for the new elements. Find the `static styles` string and add these rules before the closing backtick:

```css
        /* ── Tool cards ── */
        .tool-card {
            margin: .3rem 0; padding: .3rem .5rem;
            background: var(--surface-3, #0f3460); border-radius: .3rem;
            font-size: .75rem; border-left: 2px solid var(--accent, #4cc9f0);
        }
        .tool-header { font-weight: 600; display: flex; align-items: center; gap: .3rem; }
        .tool-icon { opacity: .6; }
        .tool-spin { animation: spin 1s linear infinite; font-size: .5rem; color: var(--accent, #4cc9f0); }
        @keyframes spin { to { transform: rotate(360deg); } }
        .tool-result { margin-top: .2rem; opacity: .7; font-size: .7rem; word-break: break-word; }

        /* ── Thinking indicator ── */
        .msg-thinking {
            font-style: italic; opacity: .5; font-size: .75rem; margin-bottom: .3rem;
        }
        .thinking-dots::after {
            content: ''; animation: dots 1.5s steps(3, end) infinite;
        }
        @keyframes dots { 0% { content: '.'; } 33% { content: '..'; } 66% { content: '...'; } }

        /* ── Stats ── */
        .msg-stats {
            font-size: .65rem; opacity: .4; margin-top: .2rem;
        }
```

## Conventions

Web components use shadow DOM with inline styles. CSS variables use the existing theme tokens (--surface-3, --accent, --text-1, --border). HTML escaping via _esc() method. Event handling follows the existing onChunk/onDone/onError pattern in HTTP.stream(). No external dependencies.

## Files

**Read:** - /workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js

**Modify:** - /workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js

**Create:** none

## Verification

**Commands:**
- `cd /workspace && node -e "import('/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js').catch(e => console.log('Module load check:', e.message))"`

**Checks:**
- _sendStream dispatches on chunk.name
- tool_call renders a compact card with tool name
- tool_result appends to matching tool card by call_id
- thinking shows animated indicator
- text still works as progressive append
- done still shows answer if no text was streamed
- CSS includes tool-card, msg-thinking, msg-stats rules
- Backward compat: unknown chunk names fall through to text handler
