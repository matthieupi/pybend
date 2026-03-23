/**
 * tx-graph.js — LiteGraph wrapper + custom actor node types.
 *
 * Manages the graph canvas, custom node types, and edge management.
 * Not a Web Component — used as a module by ntx-tx-inspector.
 */

class TxGraph {
    constructor(canvasElement) {
        this.canvasEl = canvasElement;
        this.graph = new LGraph();
        this.graphCanvas = new LGraphCanvas(canvasElement, this.graph);

        // Dark theme
        this.graphCanvas.background_color = '#0d1117';
        this.graphCanvas.clear_background_color = '#0d1117';
        LiteGraph.NODE_DEFAULT_COLOR = '#2a4858';
        LiteGraph.NODE_DEFAULT_BGCOLOR = '#1a2a38';
        LiteGraph.NODE_DEFAULT_BOXCOLOR = '#444';
        LiteGraph.DEFAULT_LINK_COLOR = '#333';
        this.graphCanvas.default_link_color = '#333';

        // Read-only interaction (can still zoom/pan/select)
        this.graphCanvas.allow_searchbox = false;
        this.graphCanvas.allow_dragnodes = true;

        // Node maps
        this._nodeMap = new Map();      // actor_id -> LGraphNode
        this._linkMap = new Map();      // "source->target" -> { link_id, tx_uuids }
        this._linkToPath = new Map();   // link_id -> "source->target"
        this._activeEdges = new Map();  // link_id -> timeout_id (for fade)

        this.graph.start();
    }

    // ── Node Types ──

    static registerNodeTypes() {
        if (TxGraph._typesRegistered) return;
        TxGraph._typesRegistered = true;

        function makeNodeType(title, color, bgcolor) {
            function NodeType() {
                this.addInput('in', 'tx');
                this.addOutput('out', 'tx');
                this.size = [180, 40];
                this.properties = { addr: '', actorType: '', txCount: 0 };
                this.color = color;
                this.bgcolor = bgcolor;
                this.flags = {};
            }
            NodeType.title = title;
            NodeType.prototype.onDrawForeground = function(ctx) {
                // TX count badge
                if (this.properties.txCount > 0) {
                    ctx.fillStyle = '#58a6ff';
                    ctx.font = '10px monospace';
                    ctx.textAlign = 'right';
                    ctx.fillText(this.properties.txCount, this.size[0] - 8, -4);
                }
            };
            return NodeType;
        }

        LiteGraph.registerNodeType('actor/matrix',  makeNodeType('Matrix',  '#3d5a80', '#253d5a'));
        LiteGraph.registerNodeType('actor/adapter', makeNodeType('Adapter', '#2a6478', '#1a3a48'));
        LiteGraph.registerNodeType('actor/model',   makeNodeType('Model',   '#2a5838', '#1a3828'));
        LiteGraph.registerNodeType('actor/agent',   makeNodeType('Agent',   '#4a2878', '#2a1858'));
    }

    // ── Topology ──

    loadTopology(topology) {
        this.graph.clear();
        this._nodeMap.clear();
        this._linkMap.clear();
        this._linkToPath.clear();

        const { nodes, edges } = topology;

        // Column layout by type
        const COLS = { matrix: 100, adapter: 300, model: 550, agent: 550 };
        const counters = { matrix: 0, adapter: 0, model: 0, agent: 0 };

        for (const n of nodes) {
            const type = n.type || 'model';
            const nodeType = `actor/${type}`;
            const node = LiteGraph.createNode(nodeType);
            if (!node) continue;

            node.title = n.label || n.id;
            node.properties.addr = n.id;
            node.properties.actorType = type;

            const col = COLS[type] || COLS.model;
            const row = counters[type] || 0;
            counters[type] = row + 1;

            node.pos = [col, 80 + row * 90];
            this.graph.add(node);
            this._nodeMap.set(n.id, node);
        }

        // Create structural edges (parent-child)
        for (const e of edges) {
            const fromNode = this._nodeMap.get(e.from);
            const toNode = this._nodeMap.get(e.to);
            if (fromNode && toNode) {
                fromNode.connect(0, toNode, 0);
            }
        }
    }

    // ── TX Edge Management ──

    addTxEdge(entry) {
        const { source, target } = this._resolveActors(entry);
        if (!source || !target || source === target) return;

        const sourceNode = this._nodeMap.get(source);
        const targetNode = this._nodeMap.get(target);
        if (!sourceNode || !targetNode) return;

        // Increment TX count on target
        targetNode.properties.txCount = (targetNode.properties.txCount || 0) + 1;

        const pathKey = `${source}->${target}`;
        let linkInfo = this._linkMap.get(pathKey);

        if (!linkInfo) {
            // Create connection if it doesn't exist
            const linkId = sourceNode.connect(0, targetNode, 0);
            linkInfo = { link_id: linkId, tx_uuids: [] };
            this._linkMap.set(pathKey, linkInfo);
            if (linkId != null) {
                this._linkToPath.set(linkId, pathKey);
            }
        }

        linkInfo.tx_uuids.push(entry.tx_uuid);

        // Animate: bright on activity, fade after 2s
        this._pulseEdge(linkInfo.link_id, entry);
    }

    _resolveActors(entry) {
        // Extract first segment of source/target addresses
        const source = (entry.source || '').split('/')[0];
        const target = (entry.target || '').split('/')[0];
        return { source, target };
    }

    _pulseEdge(linkId, entry) {
        if (linkId == null) return;
        const link = this.graph.links[linkId];
        if (!link) return;

        // Color by type
        let color = '#58a6ff';  // default blue
        if (entry.is_error) color = '#f85149';
        else if (entry.is_stream) color = '#3fb950';
        else if (entry.name === 'ERROR') color = '#f85149';

        link.color = color;
        this.graphCanvas.setDirty(true);

        // Clear previous fade timeout
        const prevTimeout = this._activeEdges.get(linkId);
        if (prevTimeout) clearTimeout(prevTimeout);

        // Fade after 2s
        const timeout = setTimeout(() => {
            if (this.graph.links[linkId]) {
                this.graph.links[linkId].color = '#333';
                this.graphCanvas.setDirty(true);
            }
            this._activeEdges.delete(linkId);
        }, 2000);
        this._activeEdges.set(linkId, timeout);
    }

    // ── Highlighting ──

    highlightEdge(txUuid) {
        this.clearHighlights();

        for (const [pathKey, info] of this._linkMap) {
            if (info.tx_uuids.includes(txUuid)) {
                const link = this.graph.links[info.link_id];
                if (link) {
                    link.color = '#58a6ff';
                    link._width = 3;
                }
            }
        }
        this.graphCanvas.setDirty(true);
    }

    highlightChain(entries) {
        this.clearHighlights();
        if (!entries.length) return;

        // Sort by timestamp
        const sorted = [...entries].sort((a, b) => a.timestamp - b.timestamp);
        const minTs = sorted[0].timestamp;
        const maxTs = sorted[sorted.length - 1].timestamp;
        const range = maxTs - minTs || 1;

        // Color gradient: red (hsl 0) → blue (hsl 240)
        const chainLinks = new Set();
        for (let i = 0; i < sorted.length; i++) {
            const e = sorted[i];
            const { source, target } = this._resolveActors(e);
            const pathKey = `${source}->${target}`;
            const linkInfo = this._linkMap.get(pathKey);
            if (linkInfo) {
                const link = this.graph.links[linkInfo.link_id];
                if (link) {
                    const t = (e.timestamp - minTs) / range;
                    const hue = Math.round(t * 240);  // 0=red, 240=blue
                    link.color = `hsl(${hue}, 80%, 60%)`;
                    link._width = 3;
                    chainLinks.add(linkInfo.link_id);
                }
            }
        }

        // Dim non-chain links
        for (const linkId in this.graph.links) {
            if (!chainLinks.has(parseInt(linkId))) {
                const link = this.graph.links[linkId];
                if (link) link.color = '#1a1a1a';
            }
        }

        this.graphCanvas.setDirty(true);
    }

    clearHighlights() {
        for (const linkId in this.graph.links) {
            const link = this.graph.links[linkId];
            if (link) {
                link.color = '#333';
                delete link._width;
            }
        }
        this.graphCanvas.setDirty(true);
    }

    resize() {
        this.canvasEl.width = this.canvasEl.parentElement.clientWidth;
        this.canvasEl.height = this.canvasEl.parentElement.clientHeight;
        this.graphCanvas.resize();
    }
}

// Register node types on load
TxGraph.registerNodeTypes();
TxGraph._typesRegistered = false;
