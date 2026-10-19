/**
 * renderer.js — Pure Canvas2D drawing functions for graph-flow.
 *
 * Draws nodes (rounded rects + labels + TX badges),
 * edges (lines + arrowheads clipped to node boundaries),
 * with HiDPI support.
 */

const ARROW_LEN = 10;
const ARROW_HALF = 6;
const NODE_RADIUS = 6;
const NODE_HEIGHT = 44;
const NODE_PAD_X = 24;
const NODE_MIN_W = 120;
const NODE_MAX_W = 220;
const BADGE_FONT = '10px monospace';
const LABEL_FONT = '13px monospace';

/**
 * Linearly interpolate between two hex colors.
 * @param {string} a - Start color (#rrggbb)
 * @param {string} b - End color (#rrggbb)
 * @param {number} t - Progress 0..1
 * @returns {string} Interpolated hex color
 */
export function lerpColor(a, b, t) {
    const ar = parseInt(a.slice(1, 3), 16);
    const ag = parseInt(a.slice(3, 5), 16);
    const ab = parseInt(a.slice(5, 7), 16);
    const br = parseInt(b.slice(1, 3), 16);
    const bg = parseInt(b.slice(3, 5), 16);
    const bb = parseInt(b.slice(5, 7), 16);
    const r = Math.round(ar + (br - ar) * t);
    const g = Math.round(ag + (bg - ag) * t);
    const bl = Math.round(ab + (bb - ab) * t);
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${bl.toString(16).padStart(2, '0')}`;
}

/**
 * Measure and set node width based on label text.
 * @param {CanvasRenderingContext2D} ctx
 * @param {object} node
 */
export function measureNode(ctx, node) {
    ctx.font = LABEL_FONT;
    const textW = ctx.measureText(node.label).width + NODE_PAD_X;
    node.width = Math.max(NODE_MIN_W, Math.min(NODE_MAX_W, textW));
    node.height = NODE_HEIGHT;
}

/**
 * Find intersection of a line (from inside rect to outside) with the rect boundary.
 * Returns the point on the rect edge.
 */
function rectLineIntersect(rx, ry, rw, rh, fromX, fromY, toX, toY) {
    const cx = rx + rw / 2;
    const cy = ry + rh / 2;
    const dx = toX - fromX;
    const dy = toY - fromY;

    if (dx === 0 && dy === 0) return { x: cx, y: cy };

    // Check each edge, find the closest intersection
    let tMin = Infinity;
    let bestX = cx, bestY = cy;

    // Left edge (x = rx)
    if (dx !== 0) {
        const t = (rx - fromX) / dx;
        if (t >= 0 && t <= 1) {
            const iy = fromY + t * dy;
            if (iy >= ry && iy <= ry + rh && t < tMin) {
                tMin = t; bestX = rx; bestY = iy;
            }
        }
    }
    // Right edge (x = rx + rw)
    if (dx !== 0) {
        const t = (rx + rw - fromX) / dx;
        if (t >= 0 && t <= 1) {
            const iy = fromY + t * dy;
            if (iy >= ry && iy <= ry + rh && t < tMin) {
                tMin = t; bestX = rx + rw; bestY = iy;
            }
        }
    }
    // Top edge (y = ry)
    if (dy !== 0) {
        const t = (ry - fromY) / dy;
        if (t >= 0 && t <= 1) {
            const ix = fromX + t * dx;
            if (ix >= rx && ix <= rx + rw && t < tMin) {
                tMin = t; bestX = ix; bestY = ry;
            }
        }
    }
    // Bottom edge (y = ry + rh)
    if (dy !== 0) {
        const t = (ry + rh - fromY) / dy;
        if (t >= 0 && t <= 1) {
            const ix = fromX + t * dx;
            if (ix >= rx && ix <= rx + rw && t < tMin) {
                tMin = t; bestX = ix; bestY = ry + rh;
            }
        }
    }

    return { x: bestX, y: bestY };
}

const CURVE_FRACTION = 0.15;   // perpendicular offset as fraction of distance
const CURVE_MIN = 15;
const CURVE_MAX = 50;
const LANE_SPACING = 20;       // pixels between parallel edges sharing a node pair

/**
 * Compute perpendicular unit vector and base curve offset for an edge.
 */
function curveOffset(dx, dy, len) {
    const offset = Math.max(CURVE_MIN, Math.min(CURVE_MAX, len * CURVE_FRACTION));
    return { px: -dy / len, py: dx / len, offset };
}

/**
 * Assign lane indices to edges so parallel edges between the same node pair
 * fan out instead of stacking. Returns a Map<pathKey, number>.
 *
 * Edges sharing an unordered pair {A,B} are grouped together.
 * Within a group of N edges, lanes go from -(N-1)/2 to +(N-1)/2.
 */
function assignLanes(edgeMap) {
    const lanes = new Map();
    const groups = new Map();   // unordered pair key → [pathKey, ...]

    for (const [pathKey, edge] of edgeMap) {
        const pairKey = edge.from < edge.to
            ? `${edge.from}\0${edge.to}`
            : `${edge.to}\0${edge.from}`;
        let group = groups.get(pairKey);
        if (!group) { group = []; groups.set(pairKey, group); }
        group.push(pathKey);
    }

    for (const group of groups.values()) {
        const n = group.length;
        for (let i = 0; i < n; i++) {
            lanes.set(group[i], i - (n - 1) / 2);
        }
    }
    return lanes;
}

/**
 * Draw arrowhead at tip, oriented along (ux, uy).
 */
function drawArrowhead(ctx, tipX, tipY, ux, uy, color) {
    const baseX = tipX - ux * ARROW_LEN;
    const baseY = tipY - uy * ARROW_LEN;
    ctx.beginPath();
    ctx.moveTo(tipX, tipY);
    ctx.lineTo(baseX - uy * ARROW_HALF, baseY + ux * ARROW_HALF);
    ctx.lineTo(baseX + uy * ARROW_HALF, baseY - ux * ARROW_HALF);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
}

/**
 * Draw edge as a straight line. Lane shifts endpoints perpendicular to create
 * parallel lines when multiple edges connect the same node pair.
 */
function drawEdgeLine(ctx, start, end, color, width, lane) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (len < 1) return;

    // Shift both endpoints perpendicular by lane
    const px = -dy / len;
    const py =  dx / len;
    const shift = lane * LANE_SPACING;
    const sx = start.x + px * shift, sy = start.y + py * shift;
    const ex = end.x   + px * shift, ey = end.y   + py * shift;

    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(ex, ey);
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();

    drawArrowhead(ctx, ex, ey, dx / len, dy / len, color);
}

/**
 * Draw edge as a quadratic Bezier. Lane shifts the control point further
 * perpendicular, fanning parallel edges apart.
 */
function drawEdgeQuadratic(ctx, start, end, color, width, lane) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (len < 1) return;

    const { px, py, offset } = curveOffset(dx, dy, len);
    const totalOffset = offset + lane * LANE_SPACING;
    const cpX = (start.x + end.x) / 2 + px * totalOffset;
    const cpY = (start.y + end.y) / 2 + py * totalOffset;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.quadraticCurveTo(cpX, cpY, end.x, end.y);
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();

    // Tangent at endpoint: CP → end
    const tdx = end.x - cpX;
    const tdy = end.y - cpY;
    const tlen = Math.sqrt(tdx * tdx + tdy * tdy);
    if (tlen < 1) return;
    drawArrowhead(ctx, end.x, end.y, tdx / tlen, tdy / tlen, color);
}

/**
 * Draw edge as a cubic Bezier (S-curve). Lane shifts both control points,
 * fanning parallel edges apart while preserving the S shape.
 */
function drawEdgeBezier(ctx, start, end, color, width, lane) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (len < 1) return;

    const { px, py, offset } = curveOffset(dx, dy, len);
    const totalOffset = offset + lane * LANE_SPACING;
    const cp1X = start.x + dx / 3 + px * totalOffset;
    const cp1Y = start.y + dy / 3 + py * totalOffset;
    const cp2X = start.x + dx * 2 / 3 - px * totalOffset;
    const cp2Y = start.y + dy * 2 / 3 - py * totalOffset;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.bezierCurveTo(cp1X, cp1Y, cp2X, cp2Y, end.x, end.y);
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();

    // Tangent at endpoint: CP2 → end
    const tdx = end.x - cp2X;
    const tdy = end.y - cp2Y;
    const tlen = Math.sqrt(tdx * tdx + tdy * tdy);
    if (tlen < 1) return;
    drawArrowhead(ctx, end.x, end.y, tdx / tlen, tdy / tlen, color);
}

const EDGE_DRAW = {
    line:      drawEdgeLine,
    quadratic: drawEdgeQuadratic,
    bezier:    drawEdgeBezier,
};

/**
 * Draw a single edge with arrowhead.
 * @param {string} edgeStyle - 'line' | 'quadratic' | 'bezier'
 * @param {number} lane - perpendicular lane index (0 = centered)
 */
function drawEdge(ctx, edge, nodeMap, edgeStyle, lane) {
    const fromNode = nodeMap.get(edge.from);
    const toNode = nodeMap.get(edge.to);
    if (!fromNode || !toNode) return;

    const fromCX = fromNode.x + fromNode.width / 2;
    const fromCY = fromNode.y + fromNode.height / 2;
    const toCX = toNode.x + toNode.width / 2;
    const toCY = toNode.y + toNode.height / 2;

    // Clip to node boundaries
    const start = rectLineIntersect(
        fromNode.x, fromNode.y, fromNode.width, fromNode.height,
        fromCX, fromCY, toCX, toCY
    );
    const end = rectLineIntersect(
        toNode.x, toNode.y, toNode.width, toNode.height,
        toCX, toCY, fromCX, fromCY
    );

    const draw = EDGE_DRAW[edgeStyle] || drawEdgeQuadratic;
    draw(ctx, start, end, edge.color || '#333', edge.width || 1.5, lane);
}

/**
 * Draw a rounded rectangle.
 */
function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
}

/**
 * Draw a single node.
 */
function drawNode(ctx, node) {
    // Background
    roundRect(ctx, node.x, node.y, node.width, node.height, NODE_RADIUS);
    ctx.fillStyle = node.bgcolor || '#1a2a38';
    ctx.fill();

    // Border
    ctx.strokeStyle = node.color || '#2a4858';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Label
    ctx.fillStyle = '#e6edf3';
    ctx.font = LABEL_FONT;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(node.label, node.x + node.width / 2, node.y + node.height / 2);

    // TX count badge (top-right)
    if (node.txCount > 0) {
        ctx.fillStyle = '#58a6ff';
        ctx.font = BADGE_FONT;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'bottom';
        ctx.fillText(String(node.txCount), node.x + node.width - 6, node.y - 3);
    }
}

/**
 * Main render function — clears canvas, draws all edges then all nodes.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {HTMLCanvasElement} canvas
 * @param {Map} nodeMap - id → node
 * @param {Map} edgeMap - pathKey → edge
 * @param {{ scale: number, offsetX: number, offsetY: number }} transform
 * @param {{ background: string }} options
 */
export function render(ctx, canvas, nodeMap, edgeMap, transform, options) {
    const { scale, offsetX, offsetY } = transform;

    // Clear
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = options.background || '#0d1117';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Apply transform
    ctx.setTransform(scale, 0, 0, scale, offsetX, offsetY);

    // Assign lanes so parallel edges between the same node pair fan out
    const lanes = assignLanes(edgeMap);

    // Draw edges first (under nodes)
    const edgeStyle = options.edgeStyle || 'quadratic';
    for (const [pathKey, edge] of edgeMap) {
        drawEdge(ctx, edge, nodeMap, edgeStyle, lanes.get(pathKey) || 0);
    }

    // Draw nodes on top
    for (const node of nodeMap.values()) {
        drawNode(ctx, node);
    }

    // Reset transform
    ctx.setTransform(1, 0, 0, 1, 0, 0);
}

/**
 * Resize canvas for HiDPI displays.
 * @param {HTMLCanvasElement} canvas
 */
export function resizeCanvas(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    return { width: rect.width, height: rect.height, dpr };
}
