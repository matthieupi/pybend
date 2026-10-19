import {config} from '../config.js';

const MAX_ENTRIES = 500;

const LOGGING_STATE = globalThis.__N3TX_LOGGING__ ||= {
    entries: [],
    listeners: [],
};

export default class Logging {

    static get size() { return LOGGING_STATE.entries.length; }

    static getEntries(filter) {
        if (!filter) return LOGGING_STATE.entries.slice();
        return LOGGING_STATE.entries.filter(e => e.level === filter);
    }

    static clear() {
        LOGGING_STATE.entries.length = 0;
        for (const fn of LOGGING_STATE.listeners) fn();
    }

    static addListener(fn) {
        LOGGING_STATE.listeners.push(fn);
    }

    static removeListener(fn) {
        LOGGING_STATE.listeners = LOGGING_STATE.listeners.filter(f => f !== fn);
    }

    static #push(level, message, detail) {
        const entry = { level, message, detail, timestamp: Date.now() };
        LOGGING_STATE.entries.push(entry);
        if (LOGGING_STATE.entries.length > MAX_ENTRIES) {
            LOGGING_STATE.entries.shift();
        }
        for (const fn of LOGGING_STATE.listeners) fn(entry);
    }

    static init(val, data) {
        if (config.LOGGING < 3) return;
        Logging.#push('info', val, data);
    }

    static log(val1, val2) {
        if (config.LOGGING < 3) return;
        Logging.#push('info', val1, val2);
    }

    static dev(val1, val2) {
        if (config.LOGGING < 4) return;
        Logging.#push('dev', val1, val2);
    }

    static event(tx) {
        if (!config.LOGEVENTS) return;
        const msg = tx.name ? `[${tx.name}] ${tx.source} --> ${tx.target}` : String(tx);
        Logging.#push('event', msg, tx.data);
    }

    static debug(val1, val2) {
        if (!config.DEBUG) return;
        Logging.#push('debug', val1, val2);
    }

    static warn(val1, val2 = "", lvl = config.LOGGING) {
        if (lvl < 2) return;
        Logging.#push('warn', val1, val2);
    }

    static error(val1, val2) {
        if (config.LOGGING < 1) return;
        Logging.#push('error', val1, val2);
    }

}
