/**
 * interaction.js — Mouse interaction for graph-flow.
 *
 * Handles zoom (wheel), pan (drag background), node drag,
 * double-click fit-to-view, and hit-testing.
 */

const ZOOM_MIN = 0.2;
const ZOOM_MAX = 3.0;
const ZOOM_FACTOR = 0.001;

export class Interaction {
    /**
     * @param {HTMLCanvasElement} canvas
     * @param {object} state - Shared state: { transform, nodeMap, dirty }
     * @param {function} onFitToView - Callback for double-click fit
     */
    constructor(canvas, state, onFitToView) {
        this._canvas = canvas;
        this._state = state;
        this._onFitToView = onFitToView;

        this._dragging = false;
        this._dragNode = null;
        this._dragStart = { x: 0, y: 0 };
        this._dragNodeStart = { x: 0, y: 0 };
        this._panStart = { x: 0, y: 0 };

        this._onWheel = this._onWheel.bind(this);
        this._onMouseDown = this._onMouseDown.bind(this);
        this._onMouseMove = this._onMouseMove.bind(this);
        this._onMouseUp = this._onMouseUp.bind(this);
        this._onDblClick = this._onDblClick.bind(this);

        canvas.addEventListener('wheel', this._onWheel, { passive: false });
        canvas.addEventListener('mousedown', this._onMouseDown);
        canvas.addEventListener('mousemove', this._onMouseMove);
        canvas.addEventListener('mouseup', this._onMouseUp);
        canvas.addEventListener('mouseleave', this._onMouseUp);
        canvas.addEventListener('dblclick', this._onDblClick);
    }

    /**
     * Convert screen coordinates to world coordinates.
     */
    screenToWorld(sx, sy) {
        const { scale, offsetX, offsetY } = this._state.transform;
        return {
            x: (sx - offsetX) / scale,
            y: (sy - offsetY) / scale,
        };
    }

    /**
     * Hit-test: find the topmost node at world coordinates.
     * Checks in reverse order (last rendered = topmost).
     */
    _hitTest(wx, wy) {
        const nodes = [...this._state.nodeMap.values()].reverse();
        for (const node of nodes) {
            if (wx >= node.x && wx <= node.x + node.width &&
                wy >= node.y && wy <= node.y + node.height) {
                return node;
            }
        }
        return null;
    }

    /**
     * Get mouse position relative to canvas.
     */
    _getPos(e) {
        const rect = this._canvas.getBoundingClientRect();
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    // ── Zoom ──

    _onWheel(e) {
        e.preventDefault();
        const { transform } = this._state;
        const pos = this._getPos(e);

        const oldScale = transform.scale;
        const delta = -e.deltaY * ZOOM_FACTOR;
        const newScale = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, oldScale * (1 + delta)));

        // Zoom toward cursor (CSS-space, DPR applied only in renderer)
        transform.offsetX = pos.x - (pos.x - transform.offsetX) * (newScale / oldScale);
        transform.offsetY = pos.y - (pos.y - transform.offsetY) * (newScale / oldScale);
        transform.scale = newScale;

        this._state.dirty = true;
    }

    // ── Mouse ──

    _onMouseDown(e) {
        const pos = this._getPos(e);
        const world = this.screenToWorld(pos.x, pos.y);
        const node = this._hitTest(world.x, world.y);

        this._dragging = true;
        this._dragStart = pos;

        if (node) {
            this._dragNode = node;
            this._dragNodeStart = { x: node.x, y: node.y };
            this._canvas.style.cursor = 'grabbing';
        } else {
            this._dragNode = null;
            this._panStart = {
                x: this._state.transform.offsetX,
                y: this._state.transform.offsetY,
            };
            this._canvas.style.cursor = 'grabbing';
        }
    }

    _onMouseMove(e) {
        const pos = this._getPos(e);

        if (!this._dragging) {
            // Hover cursor
            const world = this.screenToWorld(pos.x, pos.y);
            const node = this._hitTest(world.x, world.y);
            this._canvas.style.cursor = node ? 'grab' : 'default';
            return;
        }

        const dx = pos.x - this._dragStart.x;
        const dy = pos.y - this._dragStart.y;

        if (this._dragNode) {
            // Drag node
            const { scale } = this._state.transform;
            this._dragNode.x = this._dragNodeStart.x + dx / scale;
            this._dragNode.y = this._dragNodeStart.y + dy / scale;
        } else {
            // Pan canvas
            this._state.transform.offsetX = this._panStart.x + dx;
            this._state.transform.offsetY = this._panStart.y + dy;
        }

        this._state.dirty = true;
    }

    _onMouseUp() {
        if (this._dragging) {
            this._dragging = false;
            this._dragNode = null;
            this._canvas.style.cursor = 'default';
        }
    }

    // ── Double-click to fit ──

    _onDblClick() {
        if (this._onFitToView) this._onFitToView();
    }

    /**
     * Remove all event listeners.
     */
    destroy() {
        const c = this._canvas;
        c.removeEventListener('wheel', this._onWheel);
        c.removeEventListener('mousedown', this._onMouseDown);
        c.removeEventListener('mousemove', this._onMouseMove);
        c.removeEventListener('mouseup', this._onMouseUp);
        c.removeEventListener('mouseleave', this._onMouseUp);
        c.removeEventListener('dblclick', this._onDblClick);
    }
}
