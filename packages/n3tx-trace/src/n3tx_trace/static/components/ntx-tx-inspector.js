/**
 * ntx-tx-inspector.js — Main inspector component.
 *
 * Coordinates: GraphFlow canvas + sidebar + chain panel + entry detail panel.
 * Fetches topology + snapshot, opens SSE stream for live updates.
 *
 * Sidebar layout (vertical):
 *   tx-sidebar          — TX list (flex: 1)
 *   .resize-handle      — drag to resize chain panel
 *   tx-detail           — request chain
 *   .resize-handle      — drag to resize entry detail panel
 *   tx-entry-detail     — single TX inspector
 *
 * The sidebar itself is horizontally resizable via a handle on its left edge.
 */

class NtxTxInspector extends HTMLElement {
    constructor() {
        super();
        this._entries = [];
        this._graph = null;
        this._eventSource = null;
        this._chainEntries = null;

        // Panel heights (0 = use 50% default on first open)
        this._chainHeight = 0;
        this._entryHeight = 0;
        this._sidebarWidth = 340;

        // Drag state
        this._activeResize = null;  // 'chain' | 'entry' | 'sidebar'
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
            <div class="sidebar-resize-handle"></div>
            <div class="inspector-sidebar">
                <tx-sidebar></tx-sidebar>
                <div class="resize-handle" data-target="chain"></div>
                <tx-detail></tx-detail>
                <div class="resize-handle" data-target="entry"></div>
                <tx-entry-detail></tx-entry-detail>
            </div>
        `;

        this._canvasEl = this.querySelector('canvas');
        this._statusDot = this.querySelector('.status-dot');
        this._statusText = this.querySelector('.status-text');
        this._sidebar = this.querySelector('tx-sidebar');
        this._detail = this.querySelector('tx-detail');
        this._entryDetail = this.querySelector('tx-entry-detail');
        this._sidebarContainer = this.querySelector('.inspector-sidebar');
        this._chainHandle = this.querySelector('[data-target="chain"]');
        this._entryHandle = this.querySelector('[data-target="entry"]');
        this._sidebarHandle = this.querySelector('.sidebar-resize-handle');

        // Init GraphFlow
        this._graph = new GraphFlow(this._canvasEl);

        // ── Sidebar events ──

        this._sidebar.addEventListener('tx-hover', (e) => {
            this._graph.highlightEdge(e.detail.entry.tx_uuid);
        });

        this._sidebar.addEventListener('tx-select', (e) => {
            const traceId = e.detail.trace_id;
            const chainEntries = this._entries.filter(en => en.trace_id === traceId);
            this._graph.highlightChain(chainEntries);
            this._showChain(chainEntries);
        });

        this._sidebar.addEventListener('tx-clear', () => {
            this._graph.clearHighlights();
            this._hideChain();
            this._hideEntry();
        });

        this._sidebar.addEventListener('tx-inspect', (e) => {
            this._showEntry(e.detail.entry);
        });

        // ── Chain (tx-detail) events ──

        this._detail.addEventListener('detail-close', () => {
            this._graph.clearHighlights();
            this._hideChain();
            this._hideEntry();
        });

        this._detail.addEventListener('tx-hover', (e) => {
            this._graph.highlightEdge(e.detail.entry.tx_uuid);
        });

        this._detail.addEventListener('tx-hover-end', () => {
            if (this._chainEntries) {
                this._graph.highlightChain(this._chainEntries);
            }
        });

        this._detail.addEventListener('tx-inspect', (e) => {
            this._showEntry(e.detail.entry);
        });

        // ── Entry detail events ──

        this._entryDetail.addEventListener('entry-detail-close', () => {
            this._hideEntry();
        });

        // ── Keyboard ──

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this._graph.clearHighlights();
                this._hideChain();
                this._hideEntry();
            }
        });

        // ── Resize handles ──

        this._initResize();

        // ── Window resize ──

        window.addEventListener('resize', () => {
            this._graph.resize();
        });

        // Load data
        this._init();
    }

    // ── Chain panel ──

    _showChain(entries) {
        this._chainEntries = entries;
        this._detail.show(entries);
        this._chainHandle.classList.add('visible');

        if (!this._chainHeight) {
            this._chainHeight = Math.round(this._availableHeight() / 2);
        }
        this._applyPanelHeight(this._detail, this._chainHeight);
    }

    _hideChain() {
        this._chainEntries = null;
        this._detail.hide();
        this._chainHandle.classList.remove('visible');
        this._detail.style.height = '';
    }

    // ── Entry detail panel ──

    _showEntry(entry) {
        this._entryDetail.show(entry);
        this._entryHandle.classList.add('visible');

        if (!this._entryHeight) {
            this._entryHeight = Math.round(this._availableHeight() / 3);
        }
        this._applyPanelHeight(this._entryDetail, this._entryHeight);
    }

    _hideEntry() {
        this._entryDetail.hide();
        this._entryHandle.classList.remove('visible');
        this._entryDetail.style.height = '';
    }

    // ── Panel sizing helpers ──

    _availableHeight() {
        return this._sidebarContainer.clientHeight;
    }

    _applyPanelHeight(panel, h) {
        const total = this._availableHeight();
        const handles = 5 * (
            (this._chainHandle.classList.contains('visible') ? 1 : 0) +
            (this._entryHandle.classList.contains('visible') ? 1 : 0)
        );
        const otherPanel = panel === this._detail ? this._entryDetail : this._detail;
        const otherH = otherPanel.classList.contains('visible')
            ? (otherPanel.offsetHeight || 0) : 0;
        const minPanel = 80;
        const maxH = total - handles - otherH - minPanel;
        const clamped = Math.max(minPanel, Math.min(maxH, h));

        if (panel === this._detail) this._chainHeight = clamped;
        else this._entryHeight = clamped;

        panel.style.height = clamped + 'px';
    }

    // ── Resize drag (all handles) ──

    _initResize() {
        this._onDragMove = this._onDragMove.bind(this);
        this._onDragEnd = this._onDragEnd.bind(this);

        // Horizontal panel handles
        for (const handle of [this._chainHandle, this._entryHandle]) {
            handle.addEventListener('mousedown', (e) => {
                const target = handle.dataset.target;
                const panel = target === 'chain' ? this._detail : this._entryDetail;
                if (!panel.classList.contains('visible')) return;
                e.preventDefault();
                this._activeResize = target;
                handle.classList.add('active');
                document.addEventListener('mousemove', this._onDragMove);
                document.addEventListener('mouseup', this._onDragEnd);
            });
        }

        // Vertical sidebar width handle
        this._sidebarHandle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            this._activeResize = 'sidebar';
            this._sidebarHandle.classList.add('active');
            document.addEventListener('mousemove', this._onDragMove);
            document.addEventListener('mouseup', this._onDragEnd);
        });
    }

    _onDragMove(e) {
        if (!this._activeResize) return;

        if (this._activeResize === 'sidebar') {
            // Sidebar width: distance from right edge of viewport
            const w = window.innerWidth - e.clientX;
            const clamped = Math.max(280, Math.min(600, w));
            this._sidebarWidth = clamped;
            this._sidebarContainer.style.width = clamped + 'px';
            this._sidebarContainer.style.minWidth = clamped + 'px';
            this._graph.resize();
        } else {
            // Panel height: distance from bottom of container
            const containerRect = this._sidebarContainer.getBoundingClientRect();
            const fromBottom = containerRect.bottom - e.clientY;
            const panel = this._activeResize === 'chain' ? this._detail : this._entryDetail;

            // For chain handle: height includes entry detail below it
            if (this._activeResize === 'chain') {
                const entryH = this._entryDetail.classList.contains('visible')
                    ? this._entryDetail.offsetHeight + 5 : 0;
                this._applyPanelHeight(panel, fromBottom - entryH);
            } else {
                this._applyPanelHeight(panel, fromBottom);
            }
        }
    }

    _onDragEnd() {
        if (this._activeResize === 'sidebar') {
            this._sidebarHandle.classList.remove('active');
        } else if (this._activeResize) {
            const handle = this._activeResize === 'chain' ? this._chainHandle : this._entryHandle;
            handle.classList.remove('active');
        }
        this._activeResize = null;
        document.removeEventListener('mousemove', this._onDragMove);
        document.removeEventListener('mouseup', this._onDragEnd);
    }

    // ── Data loading ──

    async _init() {
        try {
            const [topoResp, snapResp] = await Promise.all([
                fetch('/debug/topology'),
                fetch('/debug/snapshot'),
            ]);

            const topology = await topoResp.json();
            const snapshot = await snapResp.json();

            this._graph.loadTopology(topology);

            this._entries = snapshot.entries || [];
            this._sidebar.loadEntries(this._entries);

            for (const entry of this._entries) {
                this._graph.addEdge(entry);
            }
            this._graph.clearHighlights();

            this._startStream();
            this._setStatus(true, `${topology.nodes.length} actors`);
        } catch (err) {
            console.error('TX Inspector init failed:', err);
            this._setStatus(false, 'Connection failed');
        }
    }

    _startStream() {
        if (this._eventSource) this._eventSource.close();

        this._eventSource = new EventSource('/debug/stream');

        this._eventSource.onmessage = (event) => {
            try {
                const entry = JSON.parse(event.data);
                this._entries.push(entry);
                if (this._entries.length > 2000) this._entries.shift();
                this._sidebar.addEntry(entry);
                this._graph.addEdge(entry);
            } catch (err) {
                console.error('Failed to parse SSE event:', err);
            }
        };

        this._eventSource.onerror = () => {
            this._setStatus(false, 'Disconnected');
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
        if (this._eventSource) this._eventSource.close();
        if (this._graph) this._graph.destroy();
        document.removeEventListener('mousemove', this._onDragMove);
        document.removeEventListener('mouseup', this._onDragEnd);
    }
}

customElements.define('ntx-tx-inspector', NtxTxInspector);
