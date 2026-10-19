/**
 * layout.js — Column-based auto-layout for directed graphs.
 *
 * Positions nodes into columns by type, with configurable column X positions.
 */

const DEFAULT_COLUMNS = {
    matrix:  100,
    adapter: 320,
    model:   540,
    agent:   760,
};

const Y_START = 60;
const Y_GAP = 80;

/**
 * Position nodes by type into columns.
 *
 * @param {Map} nodeMap - id → node (mutated in place: sets x, y)
 * @param {object} [columnConfig] - { type: xPosition }
 */
export function layout(nodeMap, columnConfig) {
    const cols = columnConfig || DEFAULT_COLUMNS;
    const counters = {};

    for (const node of nodeMap.values()) {
        const type = node.type || 'model';
        const col = cols[type] !== undefined ? cols[type] : cols.model;
        const row = counters[type] || 0;
        counters[type] = row + 1;

        node.x = col;
        node.y = Y_START + row * Y_GAP;
    }
}

/**
 * Compute transform to fit all nodes in view.
 *
 * @param {Map} nodeMap
 * @param {number} canvasW - Display width (CSS pixels)
 * @param {number} canvasH - Display height (CSS pixels)
 * @returns {{ offsetX: number, offsetY: number, scale: number }}
 */
export function fitToView(nodeMap, canvasW, canvasH) {
    if (nodeMap.size === 0) {
        return { offsetX: 0, offsetY: 0, scale: 1 };
    }

    let minX = Infinity, minY = Infinity;
    let maxX = -Infinity, maxY = -Infinity;

    for (const node of nodeMap.values()) {
        minX = Math.min(minX, node.x);
        minY = Math.min(minY, node.y);
        maxX = Math.max(maxX, node.x + node.width);
        maxY = Math.max(maxY, node.y + node.height);
    }

    const pad = 40;
    const graphW = maxX - minX + pad * 2;
    const graphH = maxY - minY + pad * 2;

    const scale = Math.min(canvasW / graphW, canvasH / graphH, 1.5);
    const offsetX = (canvasW - graphW * scale) / 2 - (minX - pad) * scale;
    const offsetY = (canvasH - graphH * scale) / 2 - (minY - pad) * scale;

    return { offsetX, offsetY, scale };
}
