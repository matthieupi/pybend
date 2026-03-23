/**
 * ntx-tx-inspector.js — Main inspector component.
 *
 * Coordinates: LiteGraph canvas + sidebar + detail panel.
 * Fetches topology + snapshot, opens SSE stream for live updates.
 */

class NtxTxInspector extends HTMLElement {
    constructor() {
        super();
        this._entries = [];
        this._graph = null;
        this._eventSource = null;
    }

    connectedCallback() {
        this.innerHTML = `
            <div class="inspector-canvas">
                <div class="inspector-status">
                    <span class="status-dot"></span>
                    <span class="status-text">Connecting...</span>
                </div>
                <canvas></canvas>
            </div>
            <div class="inspector-sidebar">
                <tx-sidebar></tx-sidebar>
                <tx-detail></tx-detail>
            </div>
        `;

        this._canvasEl = this.querySelector('canvas');
        this._statusDot = this.querySelector('.status-dot');
        this._statusText = this.querySelector('.status-text');
        this._sidebar = this.querySelector('tx-sidebar');
        this._detail = this.querySelector('tx-detail');

        // Size canvas
        const canvasArea = this.querySelector('.inspector-canvas');
        this._canvasEl.width = canvasArea.clientWidth;
        this._canvasEl.height = canvasArea.clientHeight;

        // Init LiteGraph
        this._graph = new TxGraph(this._canvasEl);

        // Event listeners
        this._sidebar.addEventListener('tx-hover', (e) => {
            this._graph.highlightEdge(e.detail.entry.tx_uuid);
        });

        this._sidebar.addEventListener('tx-select', (e) => {
            const traceId = e.detail.trace_id;
            const chainEntries = this._entries.filter(en => en.trace_id === traceId);
            this._graph.highlightChain(chainEntries);
            this._detail.show(chainEntries);
        });

        this._sidebar.addEventListener('tx-clear', () => {
            this._graph.clearHighlights();
            this._detail.hide();
        });

        this._detail.addEventListener('detail-close', () => {
            this._graph.clearHighlights();
        });

        // Escape to clear
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this._graph.clearHighlights();
                this._detail.hide();
            }
        });

        // Resize
        window.addEventListener('resize', () => {
            this._canvasEl.width = canvasArea.clientWidth;
            this._canvasEl.height = canvasArea.clientHeight;
            this._graph.resize();
        });

        // Load data
        this._init();
    }

    async _init() {
        try {
            // Fetch topology + snapshot in parallel
            const [topoResp, snapResp] = await Promise.all([
                fetch('/debug/topology'),
                fetch('/debug/snapshot'),
            ]);

            const topology = await topoResp.json();
            const snapshot = await snapResp.json();

            // Load graph topology
            this._graph.loadTopology(topology);

            // Load existing entries
            this._entries = snapshot.entries || [];
            this._sidebar.loadEntries(this._entries);

            // Replay edges for existing entries
            for (const entry of this._entries) {
                this._graph.addTxEdge(entry);
            }
            this._graph.clearHighlights();  // Reset edge colors after replay

            // Start SSE stream
            this._startStream();

            this._setStatus(true, `${topology.nodes.length} actors`);
        } catch (err) {
            console.error('TX Inspector init failed:', err);
            this._setStatus(false, 'Connection failed');
        }
    }

    _startStream() {
        if (this._eventSource) {
            this._eventSource.close();
        }

        this._eventSource = new EventSource('/debug/stream');

        this._eventSource.onmessage = (event) => {
            try {
                const entry = JSON.parse(event.data);
                this._entries.push(entry);
                if (this._entries.length > 2000) {
                    this._entries.shift();
                }

                this._sidebar.addEntry(entry);
                this._graph.addTxEdge(entry);
            } catch (err) {
                console.error('Failed to parse SSE event:', err);
            }
        };

        this._eventSource.onerror = () => {
            this._setStatus(false, 'Disconnected');
            // Reconnect after 3s (EventSource auto-reconnects but we update status)
            setTimeout(() => {
                if (this._eventSource.readyState === EventSource.CONNECTING) {
                    this._setStatus(false, 'Reconnecting...');
                }
            }, 1000);
        };

        this._eventSource.onopen = () => {
            this._setStatus(true, 'Live');
        };
    }

    _setStatus(connected, text) {
        this._statusDot.className = `status-dot${connected ? '' : ' disconnected'}`;
        this._statusText.textContent = text;
    }

    disconnectedCallback() {
        if (this._eventSource) {
            this._eventSource.close();
        }
    }
}

customElements.define('ntx-tx-inspector', NtxTxInspector);
