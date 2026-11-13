/** @file Responsive agent chat over schema-declared native HTTP actions.
 * NTTChat owns a memory-only draft and canonical TTX history reference.
 * NTT supplies model/method schemas; native TX transport and NTTStreamAgent
 * supply dispatch and streamed presentation. Missing HTTP metadata disables
 * sending rather than inventing a facade for internal-only agent commands.
 * Integration: supply model/uuid/method for a declared HTTP chat action. */
import { NTT } from '../core/NTT.js';
import HTTP from '../core/transport/HTTP.js';
import TX from '../core/TX.js';
import { generateId } from '../core/Utils.js';
import { permissions } from '../utils/Permissions.js';
import { NTTStreamAgent } from './ntx-stream-agent.js';

const ICON_CHAT = '<svg xmlns="http://www.w3.org/2000/svg" width="20" ' +
    'height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14' +
    'a2 2 0 0 1 2 2z"/></svg>';
const ICON_CLOSE = '<svg xmlns="http://www.w3.org/2000/svg" width="16" ' +
    'height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<line x1="18" y1="6" x2="6" y2="18"/>' +
    '<line x1="6" y1="6" x2="18" y2="18"/></svg>';
const ICON_SEND = '<svg xmlns="http://www.w3.org/2000/svg" width="16" ' +
    'height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<line x1="22" y1="2" x2="11" y2="13"/>' +
    '<polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';

/** Snapshot local authentication without publishing the token.
 * @returns {string} Private token/user/role comparison key. */
function chatSession() {
    // 0. Inaccessible token storage cannot restore an earlier private session.
    let token = null;
    try { token = localStorage.getItem('jwtToken'); } catch { /* denied */ }
    return JSON.stringify([token, permissions.user?.user_id, permissions.role]);
}

/** Retain responsive chat controls while native schemas own execution.
 * callMethod dispatches one declared HTTP action; STREAM consumes correlated
 * events. newConversation clears the history handle without sending a turn.
 * A changed login clears private state; uncertain outcomes require review. */
class NTTChat extends NTTStreamAgent {

    /** Extend the inherited agent presentation without changing its layout.
     * @returns {string[]} Native shadow stylesheet URLs. */
    get styles() {
        const parent = super.styles;
        const inherited = Array.isArray(parent) ? parent :
            parent ? [parent] : [];
        return [...inherited, new URL('./ntx-chat.css', import.meta.url).href];
    }

    #items = [];
    #selectedId = null;
    #open = false;
    #ttxRef = '';
    #pending = null;
    #uncertain = false;
    #session = null;
    #events = null;
    #watch = null;
    #deadline = null;
    #size = 'xs';
    #resizeObserver = null;
    #currentAssistantEl = null;
    #currentAssistantOutputEl = null;
    #els;

    /** Resume presentation without replaying interrupted agent work.
     * @returns {void} */
    connectedCallback() {
        // 0. Preserve native initialization and bind a private login lifetime.
        if (!this.getAttribute('method')) {
            this.setAttribute('method', 'agentic_stream');
        }
        super.connectedCallback();
        this.#syncSession();
        this.#events?.abort();
        this.#events = new AbortController();
        const options = { signal: this.#events.signal };
        this.addEventListener('click', e => e.stopPropagation(), options);
        for (const name of ['storage', 'focus']) {
            window.addEventListener(name, () => this.render(), options);
        }
        clearInterval(this.#watch);
        this.#watch = setInterval(() => this.render(), 1000);
        this.#setupResizeObserver();
    }

    /** Retire local waits; disconnection does not cancel server effects.
     * @returns {void} */
    disconnectedCallback() {
        // 0. Release observers and retain the draft for uncertain work.
        this.#events?.abort();
        clearInterval(this.#watch);
        clearTimeout(this.#deadline);
        if (this.#pending) this.#markUnknown();
        this.#resizeObserver?.disconnect();
        super.disconnectedCallback();
    }

    /** Mount the existing responsive shell once and retain its composer.
     * @returns {void} */
    prerender() {
        // 0. Preserve transcript, input identity and draft across reconnects.
        if (this.#els) return;
        this.shadowRoot.innerHTML = `
            <button class="chat-tab" aria-label="Open chat"
                >${ICON_CHAT}</button>
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title"></span>
                    <button class="panel-close" aria-label="Close"
                        >${ICON_CLOSE}</button>
                </div>
                <div class="panel-controls">
                    <select class="instance-select" aria-label="Agent instance"
                        ><option value="">Loading...</option></select>
                    <p class="chat-status" role="status"
                        aria-live="polite"></p>
                </div>
                <div class="chat-messages"></div>
                <div class="chat-input">
                    <textarea placeholder="Type your message..." rows="2"
                        aria-label="Message"></textarea>
                    <button class="send-btn" aria-label="Send"
                        >${ICON_SEND}</button>
                </div>
            </div>`;

        this.#cacheEls();
        const actions = document.createElement('div');
        this.#els.newChat = document.createElement('button');
        this.#els.newChat.type = 'button';
        this.#els.newChat.textContent = 'New chat';
        this.#els.review = document.createElement('button');
        this.#els.review.type = 'button';
        this.#els.review.textContent = 'I checked the outcome';
        this.#els.review.hidden = true;
        actions.append(this.#els.newChat, this.#els.review);
        this.#els.status.before(actions);
        this.#bindListeners();
        this.#applyPanelState();
    }

    /** Synchronize native method availability without replacing message DOM.
     * @returns {void} */
    render() {
        // 0. A stale login cannot leave private content or a live send control.
        this.#syncSession();
        const title = this.shadowRoot.querySelector('.panel-title');
        if (title) title.textContent = `${this.model} · ${this.method}`;
        this.#syncControlsVisibility();
        if (!this.#els) return;
        const available = Boolean(this.#action());
        this.#els.send.disabled = !available || Boolean(this.#pending) ||
            this.#uncertain;
        this.#els.select.disabled = Boolean(this.#pending) || this.#uncertain;
        this.#els.newChat.disabled = Boolean(this.#pending) || this.#uncertain;
        this.#els.review.hidden = !this.#uncertain;
        if (!available && !this.#pending && !this.#uncertain) {
            this.#els.status.textContent =
                'No schema-declared TTX chat action is available.';
        }
    }

    /** Resolve the selected native entity after model schema attachment.
     * @returns {void} */
    definedCallback() {
        // 0. Entity loading remains separate from method invocation.
        super.definedCallback();
        this.#resolveTargetFromRef();
        if (!this.uuid && !this.#selectedId) this.#loadInstances();
        this.#syncControlsVisibility();
    }

    /** Dispatch one explicit turn with its exact canonical history handle.
     * @returns {void} */
    callMethod() {
        // 0. Require a declared HTTP contract; never synthesize an AGENTIC API.
        if (!this.#syncSession() || !this.#els || this.#pending ||
            this.#uncertain) return;
        const task = this.#els.textarea.value;
        this.#resolveTargetFromRef();
        const action = this.#action();
        if (!task.trim() || !action) return;
        // 1. Retain the editable draft until a verified completion arrives.
        this.#appendUserMessage(task);
        this.#createAssistantMessage();
        this.resetAgentRenderState();
        this.#pending = {
            correlation: generateId(), target: action.base,
            message: task, ttxRef: this.#ttxRef, session: this.#session,
            method: this.method, actionName: action.name,
        };
        this.value = { task, ttx_ref: this.#ttxRef };
        this.#els.status.textContent = 'Sending… Closing does not cancel work.';
        try {
            this.send(new TX({
                name: action.name, source: this.addr, target: action.base,
                data: { ...this.value },
                meta: {
                    inbox: action.stream ? 'STREAM' : '_response_',
                    stream: action.stream,
                    correlation: this.#pending.correlation,
                },
            }));
            this.#deadline = setTimeout(() => this.#markUnknown(), 30000);
        } catch {
            this.#markUnknown();
        }
        this.render();
    }

    /** Accept one exact non-streaming action result.
     * @param {Object} data Native action result.
     * @param {Object} tx Native response envelope.
     * @returns {void} */
    _response_(data, tx) {
        // 0. Reject uncorrelated and changed-login replies before presentation.
        if (!this.#accepts(tx)) return;
        if (!this.#acceptCompletion(data)) return;
        this.#currentAssistantOutputEl.textContent = data.answer;
        this.#finish();
    }

    /** Validate correlation before inherited typed-event dispatch.
     * @param {Object} data Native stream event or transport completion.
     * @param {Object} tx Native response envelope.
     * @returns {void} */
    STREAM(data, tx) {
        // 0. The transport preserves request metadata for every streamed event.
        if (this.#accepts(tx)) super.STREAM(data, tx);
    }

    /** Accept the canonical history owner from a typed completion event.
     * @param {Object} data Native agent completion payload.
     * @param {Object} meta Native typed-event metadata.
     * @returns {void} */
    DONE(data, meta) {
        // 0. Only the typed completion payload owns the history identity.
        if (!this.#acceptCompletion(data)) return;
        const output = this.getAgentOutputElement();
        if (!output.querySelector('.entry-text-output') && data.answer) {
            const answer = this.escapeAgentHtml(data.answer);
            this.addAgentEntry('text-output',
                `<div class="entry-text-output-content">${answer}</div>`)
                .classList.add('entry-text-output');
        }
        super.DONE(data, meta);
        this.#finish();
    }

    /** Finish only streams with an acknowledged canonical completion.
     * @param {Object} data Native transport completion payload.
     * @returns {void} */
    STREAM_END(data) {
        // 0. Transport end alone does not prove an agent turn completed.
        if (!this.#pending) return;
        this.setThinkingState(false);
        this.flushAgentRender();
        if (!this.#pending.completed) this.#markUnknown();
        else this.#finish();
    }

    /** Retain the submitted draft after an uncertain stream failure.
     * @param {Object|string} err Native stream failure.
     * @returns {void} */
    STREAM_ERROR(err) {
        // 0. A failed stream never authorizes automatic replay.
        if (!this.#pending) return;
        super.STREAM_ERROR(err);
        this.#markUnknown();
    }

    /** Preserve uncertainty for correlated native HTTP errors.
     * @param {Object} original Original native request envelope.
     * @param {Object} tx Native error response envelope.
     * @returns {void} */
    ERROR(original, tx) {
        // 0. Error correlation belongs to the original request metadata.
        if (this.#accepts(tx, true)) this.#markUnknown();
    }

    /** Clear only local conversation history, preserving the unsent draft.
     * @returns {boolean} Whether a fresh conversation was selected locally. */
    newConversation() {
        // 0. Reset is explicit and cannot bypass an unresolved outcome.
        if (!this.#syncSession() || this.#pending || this.#uncertain) {
            return false;
        }
        this.#ttxRef = '';
        this.#els?.messages.replaceChildren();
        this.#currentAssistantEl = null;
        this.#currentAssistantOutputEl = null;
        this.resetAgentRenderState();
        if (this.#els) this.#els.status.textContent =
            'New conversation. Draft retained; nothing was sent.';
        return true;
    }

    /** Resolve the current assistant event surface without replacing it.
     * @returns {HTMLElement} Native agent-output container. */
    getAgentOutputElement() {
        if (this.#currentAssistantOutputEl) {
            this._bindAgentOutput(this.#currentAssistantOutputEl);
            return this.#currentAssistantOutputEl;
        }
        const lastAssistant = this.#els?.messages?.querySelector(
            '.msg-assistant:last-of-type .assistant-events',
        );
        if (lastAssistant) {
            this._bindAgentOutput(lastAssistant);
            return lastAssistant;
        }
        return super.getAgentOutputElement();
    }

    /** Reuse the current assistant surface for completion usage metadata.
     * @returns {HTMLElement} Native agent-footer container. */
    getAgentFooterElement() {
        return this.#currentAssistantOutputEl || super.getAgentFooterElement();
    }

    /** Clear only the active assistant event surface before a turn.
     * @returns {void} */
    prepareAgentOutput() {
        const output = this.getAgentOutputElement();
        if (output) output.innerHTML = '';
    }

    /** Reveal the latest event in the retained transcript.
     * @returns {void} */
    scrollAgentToBottom() {
        const messages = this.#els?.messages;
        if (messages) messages.scrollTop = messages.scrollHeight;
    }

    /** Resolve stable shell controls after first mount.
     * @returns {void} */
    #cacheEls() {
        this.#els = {
            tab: this.shadowRoot.querySelector('.chat-tab'),
            panel: this.shadowRoot.querySelector('.panel'),
            close: this.shadowRoot.querySelector('.panel-close'),
            controls: this.shadowRoot.querySelector('.panel-controls'),
            select: this.shadowRoot.querySelector('.instance-select'),
            messages: this.shadowRoot.querySelector('.chat-messages'),
            textarea: this.shadowRoot.querySelector('textarea'),
            send: this.shadowRoot.querySelector('.send-btn'),
            status: this.shadowRoot.querySelector('.chat-status'),
        };
    }

    /** Bind explicit local controls without automatic agent execution.
     * @returns {void} */
    #bindListeners() {
        // 0. Open/close affect presentation only; Send remains explicit.
        this.#els.tab.addEventListener('click', () => this.#toggle(true));
        this.#els.close.addEventListener('click', () => this.#toggle(false));
        this.#els.send.addEventListener('click', () => this.callMethod());
        this.#els.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.callMethod();
            }
        });
        this.#els.select.addEventListener('change', () => {
            if (this.#pending || this.#uncertain ||
                this.#els.textarea.value) {
                this.#els.select.value = this.#selectedId || '';
                this.#els.status.textContent =
                    'Finish or clear this draft before switching agents.';
                return;
            }
            this.#selectedId = this.#els.select.value;
            this.newConversation();
            this.render();
        });
        this.#els.newChat.addEventListener('click',
            () => this.newConversation());
        this.#els.review.addEventListener('click', () => {
            if (this.#pending) return;
            this.#uncertain = false;
            this.#els.status.textContent =
                'Nothing retried. Send only if another turn is intended.';
            this.render();
        });
    }

    /** Toggle the compact overlay without cancelling or resetting work.
     * @param {boolean} [nextOpen=!this.#open] Desired compact-panel visibility.
     * @returns {void} */
    #toggle(nextOpen = !this.#open) {
        if (this.#size !== 'xs') return;
        this.#open = nextOpen;
        this.#applyPanelState();
        if (this.#open) this.#els.textarea.focus();
    }

    /** Reflect the existing responsive inline/overlay presentation.
     * @returns {void} */
    #applyPanelState() {
        const inline = this.#size !== 'xs';
        this.toggleAttribute('data-inline', inline);
        this.setAttribute('data-size', this.#size);
        this.#els?.panel.classList.toggle('open', inline || this.#open);
        this.#els?.tab.classList.toggle('hidden', inline || this.#open);
        this.#els?.close.classList.toggle('hidden', inline);
    }

    /** Hide instance selection only when an explicit fixed entity is supplied.
     * @returns {void} */
    #syncControlsVisibility() {
        if (!this.#els) return;
        const hasFixedRef = !!(this.getAttribute('ref') || this.uuid);
        this.#els.select.hidden = hasFixedRef;
    }

    /** Bind the existing native entity selected through a fixed reference.
     * @returns {void} */
    #resolveTargetFromRef() {
        const ref = this.getAttribute('ref') || '';
        if (!ref || this.uuid) return;
        const id = ref.includes('/') ? ref.split('/').pop() : ref;
        if (!id) return;
        this.#selectedId = id;
        this.uuid = id;
        this.ntt = NTT.get(this.model + '/' + id);
    }

    /** Observe the existing responsive container without remounting controls.
     * @returns {void} */
    #setupResizeObserver() {
        // 0. Preserve the widget's existing responsive thresholds and layout.
        const observedEl = this.parentElement || this;
        this.#resizeObserver?.disconnect();
        this.#resizeObserver = new ResizeObserver((entries) => {
            const containerWidth = entries[0]?.contentRect?.width ||
                observedEl.getBoundingClientRect().width || window.innerWidth;
            const width = Math.min(containerWidth || window.innerWidth,
                window.innerWidth || containerWidth);
            const nextSize = this.#computeSize(width);
            if (nextSize === this.#size) return;
            this.#size = nextSize;
            this.#open = nextSize !== 'xs';
            this.#applyPanelState();
        });
        this.#resizeObserver.observe(observedEl);
        const initialContainerWidth =
            observedEl.getBoundingClientRect().width || window.innerWidth;
        const initialWidth = Math.min(
            initialContainerWidth || window.innerWidth,
            window.innerWidth || initialContainerWidth,
        );
        this.#size = this.#computeSize(initialWidth);
        this.#open = this.#size !== 'xs';
        this.#applyPanelState();
    }

    /** Select the existing responsive size for the available width.
     * @param {number} width Available container width in pixels.
     * @returns {string} Native responsive size alias. */
    #computeSize(width) {
        if (width < 640) return 'xs';
        if (width < 768) return 'sm';
        if (width < 1024) return 'md';
        if (width < 1280) return 'lg';
        return 'xl';
    }

    /** Load one bounded native entity page for explicit instance selection.
     * @returns {void} */
    #loadInstances() {
        // 0. Resolve collections from schema identity, not guessed table names.
        const schema = this.proto?.schema;
        if (!schema?.$id || !this.#els) return;
        const session = chatSession();
        const current = () => this.isConnected && session === chatSession() &&
            schema === this.proto?.schema;
        HTTP.get(`${schema.$id}/_?limit=20&depth=0`, resp => {
            if (!current() || !Array.isArray(resp?.data)) return;
            this.#items = resp.data.filter(item =>
                item?.$id === `${schema.$id}/${item.id}` &&
                Number.isSafeInteger(item.id) && item.id > 0);
            this.#els.select.replaceChildren(...this.#items.map(item => {
                const option = document.createElement('option');
                option.value = String(item.id);
                option.textContent = item.name || item.title || `#${item.id}`;
                return option;
            }));
            if (this.#items.length) {
                this.#selectedId = String(this.#items[0].id);
            }
            this.render();
        }, () => {
            if (!current()) return;
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'No instances';
            this.#els.select.replaceChildren(option);
        });
    }

    /** Append the explicit submitted text without interpreting it as HTML.
     * @param {string} text Submitted draft.
     * @returns {void} */
    #appendUserMessage(text) {
        const el = document.createElement('div');
        el.className = 'msg msg-user';
        el.innerHTML = '<span class="msg-role">user</span>' +
            `<span class="msg-text">${this.escapeAgentHtml(text)}</span>`;
        this.#els.messages.appendChild(el);
        this.scrollAgentToBottom();
    }

    /** Append a stable assistant surface for native streamed entries.
     * @returns {void} */
    #createAssistantMessage() {
        const el = document.createElement('div');
        el.className = 'msg msg-assistant';
        el.innerHTML = `
            <span class="msg-role">assistant</span>
            <div class="assistant-events"></div>`;
        this.#els.messages.appendChild(el);
        this.#currentAssistantEl = el;
        this.#currentAssistantOutputEl =
            el.querySelector('.assistant-events');
        this.scrollAgentToBottom();
    }

    /** Resolve only the runtime-declared canonical-history HTTP action.
     * @returns {Object|null} Declared native route descriptor, if available. */
    #action() {
        // 0. Internal-only agent methods are not browser-callable contracts.
        const schema = this.proto?.schema;
        const method = schema?.methods?.[this.method];
        const id = this.uuid || this.#selectedId;
        if (!schema?.$id || !method?.methods?.includes('POST') ||
            method.access?.rule === 'never' ||
            !/^\/[a-z][a-z0-9_]*$/i.test(method.route || '') ||
            method.parameters?.task?.type !== 'string' ||
            method.parameters?.ttx_ref?.type !== 'string' ||
            (method.requires_instance && !id) ||
            !permissions.canAction({ [this.method]: method.access },
                this.method, this.ntt?.value)) return null;
        return {
            base: method.requires_instance ? `${schema.$id}/${id}` : schema.$id,
            name: method.route.slice(1), stream: Boolean(method.stream),
        };
    }

    /** Validate a canonical local TTX identity without reading its entity.
     * @param {unknown} value Candidate completion history reference.
     * @returns {boolean} Whether this is an exact local canonical TTX URL. */
    #historyReference(value) {
        // 0. The runtime model schema supplies the API namespace.
        if (typeof value !== 'string') return false;
        try {
            const base = new URL(this.proto.schema.$id);
            const url = new URL(value);
            const prefix = base.pathname.slice(0,
                base.pathname.lastIndexOf('/') + 1);
            return ['http:', 'https:'].includes(url.protocol) &&
                url.origin === base.origin && value === url.href &&
                !url.username && !url.password && !url.search && !url.hash &&
                url.pathname.startsWith(prefix) &&
                /^TTX\/[1-9]\d*$/.test(url.pathname.slice(prefix.length));
        } catch {
            return false;
        }
    }

    /** Retire every private draft/result after any local login replacement.
     * @returns {boolean} Whether the previous login remains current. */
    #syncSession() {
        // 0. Token replacement invalidates replies even for the same user.
        const current = chatSession();
        if (this.#session === null) {
            this.#session = current;
            return true;
        }
        if (this.#session === current) return true;
        this.#session = current;
        clearTimeout(this.#deadline);
        this.#pending = null;
        this.#ttxRef = '';
        this.#uncertain = false;
        this.#selectedId = null;
        this.#items = [];
        this.value = {};
        this.response = null;
        this.resetAgentRenderState();
        this.#currentAssistantEl = null;
        this.#currentAssistantOutputEl = null;
        if (this.#els) {
            this.#els.messages.replaceChildren();
            this.#els.textarea.value = '';
            this.#els.select.replaceChildren();
            this.#els.status.textContent =
                'Login changed. Reopen chat to continue.';
        }
        return false;
    }

    /** Bind a response to the exact caller, route and current request.
     * @param {Object} tx Native response envelope.
     * @param {boolean} [error=false] Read original failed-request correlation.
     * @returns {boolean} Whether the pending request accepts this response. */
    #accepts(tx, error = false) {
        // 0. Session checks happen before any event or transcript mutation.
        if (!this.#syncSession() || !this.isConnected || !this.#pending) {
            return false;
        }
        const sent = this.#pending;
        const meta = error ? tx?.data?.meta : tx?.meta;
        const action = this.#action();
        return meta?.correlation === sent.correlation &&
            tx?.source === sent.target && tx?.target === this.addr &&
            sent.session === this.#session &&
            sent.method === this.method && action?.name === sent.actionName &&
            action.base === sent.target;
    }

    /** Accept one typed completion without guessing alternative envelopes.
     * @param {Object} data Native agent result or done-event payload.
     * @returns {boolean} Whether identity and answer are verified. */
    #acceptCompletion(data) {
        // 0. Continuation must return the exact submitted history owner.
        const sent = this.#pending;
        if (!sent || !this.#historyReference(data?.ttx_ref) ||
            (sent.ttxRef && sent.ttxRef !== data.ttx_ref) ||
            typeof data.answer !== 'string') {
            this.#markUnknown();
            return false;
        }
        this.#ttxRef = data.ttx_ref;
        sent.completed = true;
        sent.failed = data.status === 'error' || Boolean(data.error);
        if (sent.failed) this.#retainSubmission();
        if (!sent.failed && this.#els.textarea.value === sent.message) {
            this.#els.textarea.value = '';
        }
        return true;
    }

    /** Finish an acknowledged turn without claiming rollback or task success.
     * @returns {void} */
    #finish() {
        // 0. Failed acknowledged turns still require effect review.
        clearTimeout(this.#deadline);
        this.#uncertain = Boolean(this.#pending?.failed);
        this.#pending = null;
        this.#els.status.textContent = this.#uncertain
            ? 'Turn failed. Review saved effects before sending again.'
            : 'Turn completed.';
        this.#currentAssistantEl = null;
        this.#currentAssistantOutputEl = null;
        this.render();
    }

    /** Preserve drafts and block sends after unacknowledged dispatch outcomes.
     * @returns {void} */
    #markUnknown() {
        // 0. Ending the local wait never cancels or retries remote work.
        clearTimeout(this.#deadline);
        this.#retainSubmission();
        this.#pending = null;
        this.#uncertain = true;
        if (this.#els) this.#els.status.textContent =
            'Outcome unknown. Draft retained. Review records before another ' +
            'turn; nothing will be retried automatically.';
        this.render();
    }

    /** Preserve submitted text alongside edits made while a turn was pending.
     * @returns {void} */
    #retainSubmission() {
        // 0. Uncertain execution cannot silently replace the submitted draft.
        const message = this.#pending?.message;
        if (!message || !this.#els) return;
        const draft = this.#els.textarea.value;
        if (draft !== message && !draft.startsWith(`${message}\n\n`)) {
            this.#els.textarea.value = draft
                ? `${message}\n\n${draft}` : message;
        }
    }
}

customElements.define('ntx-chat', NTTChat);
export { NTTChat };

/* Changelog
 * - 2026-11-11: Use canonical TTX refs and runtime-declared HTTP routes.
 *   - Retain drafts, correlate replies and clear private state on login change.
 *   - Keep explicit reset/review controls; never retry uncertain outcomes. */
