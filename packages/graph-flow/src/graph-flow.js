/**
 * graph-flow.js — Zero-dependency Canvas2D directed graph visualization.
 *
 * Public API:
 *   new GraphFlow(canvas, options?)
 *   .loadTopology({ nodes, edges })
 *   .addEdge(entry)
 *   .highlightEdge(txUuid)
 *   .highlightChain(entries)
 *   .clearHighlights()
 *   .resize()
 *   .destroy()
 */

import { render, resizeCanvas, measureNode, lerpColor } from './renderer.js';
import { layout, fitToView } from './layout.js';
import { Interaction } from './interaction.js';

const DEFAULT_OPTIONS = {
    background: '#0d1117',
    dimEdgeColor: '#333',
    edgeFadeMs: 2000,
    edgeStyle: 'quadratic',     // 'line' | 'quadratic' | 'bezier'
    nodeColors: {
        matrix:  { color: '#3d5a80', bgcolor: '#253d5a' },
        adapter: { color: '#2a6478', bgcolor: '#1a3a48' },
        model:   { color: '#2a5838', bgcolor: '#1a3828' },
        agent:   { color: '#4a2878', bgcolor: '#2a1858' },
    },
};

export class GraphFlow {
    /**
     * @param {HTMLCanvasElement} canvas
     * @param {object} [options]
     */
    constructor(canvas, options) {
        this._canvas = canvas;
        this._ctx = canvas.getContext('2d');
        this._options = { ...DEFAULT_OPTIONS, ...options };
        if (options && options.nodeColors) {
            this._options.nodeColors = { ...DEFAULT_OPTIONS.nodeColors, ...options.nodeColors };
        }

        // State
        this._nodeMap = new Map();     // id → node
        this._edgeMap = new Map();     // pathKey → edge
        this._displayW = 0;
        this._displayH = 0;

        this._state = {
            transform: { scale: 1, offsetX: 0, offsetY: 0 },
            nodeMap: this._nodeMap,
            dirty: true,
        };

        // Interaction
        this._interaction = new Interaction(
            canvas, this._state,
            () => this._fitToView()
        );

        // Animation
        this._animFrameId = null;
        this._destroyed = false;

        // Initial sizing
        this.resize();
        this._tick = this._tick.bind(this);
        this._animFrameId = requestAnimationFrame(this._tick);
    }

    // ── Public API ──

    /**
     * Load actor topology — creates nodes + structural edges.
     * @param {{ nodes: Array, edges: Array }} topology
     */
    loadTopology(topology) {
        this._nodeMap.clear();
        this._edgeMap.clear();

        const { nodes, edges } = topology;

        // Create nodes
        for (const n of nodes) {
            const type = n.type || 'model';
            const colors = this._options.nodeColors[type] || this._options.nodeColors.model;
            const node = {
                id: n.id,
                label: n.label || n.id,
                type,
                x: 0,
                y: 0,
                width: 0,
                height: 0,
                color: colors.color,
                bgcolor: colors.bgcolor,
                txCount: 0,
            };
            this._nodeMap.set(n.id, node);
        }

        // Measure text widths
        for (const node of this._nodeMap.values()) {
            measureNode(this._ctx, node);
        }

        // Auto-layout
        layout(this._nodeMap);

        // Structural edges (parent→child)
        for (const e of edges) {
            const pathKey = `${e.from}->${e.to}`;
            if (!this._edgeMap.has(pathKey)) {
                this._edgeMap.set(pathKey, {
                    from: e.from,
                    to: e.to,
                    color: this._options.dimEdgeColor,
                    width: 1.5,
                    pulseTime: 0,
                    pulseColor: null,
                    txUuids: [],
                    pathKey,
                });
            }
        }

        this._fitToView();
        this._state.dirty = true;
    }

    /**
     * Add a TX edge (or pulse an existing one).
     * @param {{ source: string, target: string, tx_uuid: string, is_error: boolean, is_stream: boolean, name: string }} entry
     */
    addEdge(entry) {
        const source = (entry.source || '').split('/')[0];
        const target = (entry.target || '').split('/')[0];
        if (!source || !target || source === target) return;

        const sourceNode = this._nodeMap.get(source);
        const targetNode = this._nodeMap.get(target);
        if (!sourceNode || !targetNode) return;

        // Increment TX count on target
        targetNode.txCount = (targetNode.txCount || 0) + 1;

        const pathKey = `${source}->${target}`;
        let edge = this._edgeMap.get(pathKey);

        if (!edge) {
            edge = {
                from: source,
                to: target,
                color: this._options.dimEdgeColor,
                width: 1.5,
                pulseTime: 0,
                pulseColor: null,
                txUuids: [],
                pathKey,
            };
            this._edgeMap.set(pathKey, edge);
        }

        edge.txUuids.push(entry.tx_uuid);

        // Pulse color by type
        let pulseColor = '#58a6ff';  // default blue
        if (entry.is_error || entry.name === 'ERROR') pulseColor = '#f85149';
        else if (entry.is_stream) pulseColor = '#3fb950';

        edge.pulseColor = pulseColor;
        edge.color = pulseColor;
        edge.pulseTime = performance.now();
        edge.width = 2.5;

        this._state.dirty = true;
    }

    /**
     * Highlight all edges containing a specific TX UUID.
     * @param {string} txUuid
     */
    highlightEdge(txUuid) {
        this.clearHighlights();
        for (const edge of this._edgeMap.values()) {
            if (edge.txUuids.includes(txUuid)) {
                edge.color = '#58a6ff';
                edge.width = 3;
            }
        }
        this._state.dirty = true;
    }

    /**
     * Highlight a chain of entries with a time-based color gradient.
     * @param {Array} entries
     */
    highlightChain(entries) {
        this.clearHighlights();
        if (!entries || !entries.length) return;

        const sorted = [...entries].sort((a, b) => a.timestamp - b.timestamp);
        const minTs = sorted[0].timestamp;
        const maxTs = sorted[sorted.length - 1].timestamp;
        const range = maxTs - minTs || 1;

        const chainPaths = new Set();

        for (const e of sorted) {
            const source = (e.source || '').split('/')[0];
            const target = (e.target || '').split('/')[0];
            const pathKey = `${source}->${target}`;
            const edge = this._edgeMap.get(pathKey);
            if (edge) {
                const t = (e.timestamp - minTs) / range;
                const hue = Math.round(t * 240); // 0=red, 240=blue
                edge.color = `hsl(${hue}, 80%, 60%)`;
                edge.width = 3;
                chainPaths.add(pathKey);
            }
        }

        // Dim non-chain edges
        for (const [pathKey, edge] of this._edgeMap) {
            if (!chainPaths.has(pathKey)) {
                edge.color = '#1a1a1a';
            }
        }

        this._state.dirty = true;
    }

    /**
     * Reset all edge colors to resting state.
     */
    clearHighlights() {
        for (const edge of this._edgeMap.values()) {
            edge.color = this._options.dimEdgeColor;
            edge.width = 1.5;
            edge.pulseTime = 0;
            edge.pulseColor = null;
        }
        this._state.dirty = true;
    }

    /**
     * Resize canvas to fill parent container.
     */
    resize() {
        const { width, height } = resizeCanvas(this._canvas);
        this._displayW = width;
        this._displayH = height;
        this._state.dirty = true;
    }

    /**
     * Cleanup: stop animation loop, remove event listeners.
     */
    destroy() {
        this._destroyed = true;
        if (this._animFrameId) {
            cancelAnimationFrame(this._animFrameId);
        }
        this._interaction.destroy();
    }

    // ── Internal ──

    _fitToView() {
        const fit = fitToView(this._nodeMap, this._displayW, this._displayH);
        this._state.transform.scale = fit.scale;
        this._state.transform.offsetX = fit.offsetX;
        this._state.transform.offsetY = fit.offsetY;
        this._state.dirty = true;
    }

    _tick() {
        if (this._destroyed) return;

        // Update edge fade animations
        const now = performance.now();
        const fadeMs = this._options.edgeFadeMs;
        let anyFading = false;

        for (const edge of this._edgeMap.values()) {
            if (edge.pulseTime > 0) {
                const elapsed = now - edge.pulseTime;
                if (elapsed >= fadeMs) {
                    // Fade complete
                    edge.color = this._options.dimEdgeColor;
                    edge.width = 1.5;
                    edge.pulseTime = 0;
                    edge.pulseColor = null;
                    this._state.dirty = true;
                } else {
                    // Lerp color
                    const t = elapsed / fadeMs;
                    edge.color = lerpColor(
                        edge.pulseColor || '#58a6ff',
                        this._options.dimEdgeColor,
                        t
                    );
                    edge.width = 2.5 - t;  // 2.5 → 1.5
                    anyFading = true;
                    this._state.dirty = true;
                }
            }
        }

        if (this._state.dirty) {
            const dpr = window.devicePixelRatio || 1;
            // Scale transform for HiDPI
            const t = this._state.transform;
            const scaledTransform = {
                scale: t.scale * dpr,
                offsetX: t.offsetX * dpr,
                offsetY: t.offsetY * dpr,
            };
            render(
                this._ctx, this._canvas,
                this._nodeMap, this._edgeMap,
                scaledTransform, this._options
            );
            if (!anyFading) {
                this._state.dirty = false;
            }
        }

        this._animFrameId = requestAnimationFrame(this._tick);
    }
}
