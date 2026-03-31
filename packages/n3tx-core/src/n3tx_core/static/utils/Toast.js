/**
 * Toast notification utility.
 *
 * Provides lightweight, temporary floating messages for user feedback.
 * Uses CSS custom properties from the existing theme (dark-theme.css /
 * light-theme.css) so it adapts automatically to the active theme.
 *
 * Usage:
 *   import { showToast } from '../utils/Toast.js';
 *   showToast('Something went wrong', 'error');
 *   showToast('Saved successfully', 'success');
 *   showToast('Loading data...', 'info');
 */

const TOAST_DURATION = 4000;   // Auto-dismiss after 4 seconds
const FADE_DURATION  = 300;    // CSS transition length (ms)
const TOAST_GAP      = 8;     // Vertical gap between stacked toasts (px)
const TOAST_STYLES_URL = new URL('./Toast.css', import.meta.url).href;

let container = null;

/**
 * Lazily create and return the toast container element.
 * Appended to document.body on first call.
 */
function getContainer() {
    if (container && container.isConnected) return container;

    container = document.createElement('div');
    container.id = 'ntx-toast-container';
    Object.assign(container.style, {
        position: 'fixed',
        bottom: '1.5rem',
        right: '1.5rem',
        display: 'flex',
        flexDirection: 'column-reverse',
        gap: `${TOAST_GAP}px`,
        zIndex: '10000',
        pointerEvents: 'none',
    });
    document.body.appendChild(container);
    return container;
}

/**
 * Inject the toast stylesheet into <head> (once).
 */
let styleInjected = false;
function injectStyles() {
    if (styleInjected) return;
    styleInjected = true;

    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = TOAST_STYLES_URL;
    document.head.appendChild(link);
}

/**
 * Show a temporary toast notification.
 *
 * @param {string} message - The message to display.
 * @param {'error'|'success'|'info'} [type='error'] - Visual style.
 * @param {number} [duration=TOAST_DURATION] - Auto-dismiss delay in ms.
 * @returns {HTMLElement} The toast element (for programmatic removal).
 */
export function showToast(message, type = 'error', duration = TOAST_DURATION) {
    if (!message) return null;

    injectStyles();
    const box = getContainer();

    const toast = document.createElement('div');
    toast.className = `ntx-toast ntx-toast--${type}`;
    toast.textContent = String(message);
    box.appendChild(toast);

    // Trigger entrance animation on next frame
    requestAnimationFrame(() => {
        toast.classList.add('ntx-toast--visible');
    });

    // Schedule removal
    const timerId = setTimeout(() => dismiss(toast), duration);

    // Allow click to dismiss early
    toast.addEventListener('click', () => {
        clearTimeout(timerId);
        dismiss(toast);
    });

    return toast;
}

/**
 * Dismiss a toast with a fade-out animation.
 * @param {HTMLElement} toast
 */
function dismiss(toast) {
    if (!toast || !toast.isConnected) return;
    toast.classList.remove('ntx-toast--visible');
    setTimeout(() => {
        if (toast.isConnected) toast.remove();
    }, FADE_DURATION);
}

/**
 * Remove all active toasts immediately.
 * Useful in tests or page transitions.
 */
export function clearToasts() {
    if (container && container.isConnected) {
        container.innerHTML = '';
    }
}
