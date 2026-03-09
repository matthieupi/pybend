/**
 * NTTChatView — Main chat area.
 *
 * Extends NTTElement. Bound to the selected conversation.
 * Renders header + message list + ntx-chat-input.
 * Listens for user-message, stream-chunk, stream-done from the input.
 */
import { NTTElement } from './NTTElement.js';
import HTTP from '../core/transport/HTTP.js';

export class NTTChatView extends NTTElement {

  #messages = [];
  #streamText = '';
  #streaming = false;

  get styles() { return new URL('./ntx-chat-view.css', import.meta.url).href; }

  constructor() {
    super();
    // Provide a minimal schema so render() can proceed without NTT attach
    this.schema = { __name__: 'Conversation', properties: {} };
  }

  /** Escape HTML. */
  #esc(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
  }

  /** Render markdown. Falls back to escaped text. */
  #renderMarkdown(text) {
    if (window.marked) {
      try { return window.marked.parse(text); } catch {}
    }
    return `<p>${this.#esc(text)}</p>`;
  }

  /** Load a conversation by its API href/ref. Called externally. */
  loadConversation(ref) {
    // Normalize ref to full URL
    const url = ref.startsWith('http') ? ref : `${window.location.origin}/${ref}`;
    HTTP.get(url,
      (data) => {
        this.value = data;
        this.#loadMessages(url);
      },
      (err) => console.error('Failed to load conversation', err),
    );
  }

  /** Fetch messages from the join route. */
  #loadMessages(convUrl) {
    HTTP.get(`${convUrl}/messages`,
      (data) => {
        const items = data?.data || data || [];
        this.#messages = items.filter(m => m.role !== 'system' && m.content);
        this.#streamText = '';
        this.#streaming = false;
        this.#renderFull();
      },
      (err) => {
        console.error('Failed to load messages', err);
        this.#messages = [];
        this.#renderFull();
      },
    );
  }

  /** Full render — header + messages + input. */
  #renderFull() {
    const v = this.value || {};
    const name = this.#esc(v.name || 'Chat');
    const llm = this.#esc(v.llm || 'default');
    const convRef = v.href || (v.id ? `${window.location.origin}/conversations/${v.id}` : '');

    this.shadowRoot.innerHTML = `
      <div class="chat-header">
        <span class="chat-title">${name}</span>
        <span class="model-badge">${llm}</span>
      </div>
      <div class="messages" id="messageList">
        ${this.#messages.length === 0 && !this.#streaming
          ? '<div class="empty-state">No messages yet. Say hello!</div>'
          : this.#renderMessages()
        }
      </div>
      <ntx-chat-input id="chatInput"></ntx-chat-input>
    `;

    // Wire the input component
    const input = this.shadowRoot.getElementById('chatInput');
    if (input && convRef) {
      input.conversationRef = convRef;
    }

    // Bind events from input
    this.shadowRoot.addEventListener('user-message', (e) => this.#onUserMessage(e.detail));
    this.shadowRoot.addEventListener('stream-chunk', (e) => this.#onStreamChunk(e.detail));
    this.shadowRoot.addEventListener('stream-done', (e) => this.#onStreamDone(e.detail));

    // Scroll to bottom
    this.#scrollToBottom();
  }

  /** Render all message bubbles as HTML. */
  #renderMessages() {
    let html = this.#messages.map(m => {
      const role = m.role || 'user';
      const body = role === 'assistant'
        ? this.#renderMarkdown(m.content)
        : this.#esc(m.content);
      return `<div class="chat-bubble ${role}">${body}</div>`;
    }).join('');

    // Streaming bubble
    if (this.#streaming || this.#streamText) {
      const body = this.#renderMarkdown(this.#streamText || '');
      html += `<div class="chat-bubble assistant streaming" id="streamBubble">
        ${body}${this.#streaming ? '<span class="stream-cursor">|</span>' : ''}
      </div>`;
    }

    return html;
  }

  /** User sent a message — show it immediately. */
  #onUserMessage(detail) {
    this.#messages.push({ role: 'user', content: detail.content });
    this.#streamText = '';
    this.#streaming = true;

    // Remove empty state and append user bubble + streaming bubble
    const list = this.shadowRoot.getElementById('messageList');
    if (!list) return;
    const empty = list.querySelector('.empty-state');
    if (empty) empty.remove();

    // User bubble
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-bubble user';
    userDiv.textContent = detail.content;
    list.appendChild(userDiv);

    // Streaming bubble (initially empty with cursor)
    const streamDiv = document.createElement('div');
    streamDiv.className = 'chat-bubble assistant streaming';
    streamDiv.id = 'streamBubble';
    streamDiv.innerHTML = '<span class="stream-cursor">|</span>';
    list.appendChild(streamDiv);

    this.#scrollToBottom();
  }

  /** Streaming token arrived — update streaming bubble surgically. */
  #onStreamChunk(detail) {
    const text = detail?.text || '';
    this.#streamText += text;

    const bubble = this.shadowRoot.getElementById('streamBubble');
    if (bubble) {
      const body = this.#renderMarkdown(this.#streamText);
      bubble.innerHTML = `${body}<span class="stream-cursor">|</span>`;
      this.#scrollToBottom();
    }
  }

  /** Streaming complete — reload messages from server for persisted records. */
  #onStreamDone(detail) {
    this.#streaming = false;

    if (detail?.error) {
      const bubble = this.shadowRoot.getElementById('streamBubble');
      if (bubble) {
        bubble.innerHTML = `<div class="stream-error">Error: ${this.#esc(detail.error)}</div>`;
      }
      return;
    }

    // Reload messages from server to get proper persisted records
    const v = this.value || {};
    const convUrl = v.href || (v.id ? `${window.location.origin}/conversations/${v.id}` : '');
    if (convUrl) {
      this.#loadMessages(convUrl);
    }
  }

  #scrollToBottom() {
    requestAnimationFrame(() => {
      const list = this.shadowRoot.getElementById('messageList');
      if (list) list.scrollTop = list.scrollHeight;
    });
  }

  /** Override NTTElement.render() — we manage our own rendering. */
  render() {
    if (!this.value || !this.value.id) {
      this.shadowRoot.innerHTML = `
        <div class="empty-state">Select or create a conversation to start chatting.</div>
      `;
      return;
    }
    this.#renderFull();
  }
}

customElements.define('ntx-chat-view', NTTChatView);
