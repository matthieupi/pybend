import {config} from '../config.js';

const MAX_ENTRIES = 500;

export default class Logging {

    static #entries = [];
    static #listeners = [];

    static get size() { return Logging.#entries.length; }

    static getEntries(filter) {
        if (!filter) return Logging.#entries.slice();
        return Logging.#entries.filter(e => e.level === filter);
    }

    static clear() {
        Logging.#entries.length = 0;
        for (const fn of Logging.#listeners) fn();
    }

    static addListener(fn) {
        Logging.#listeners.push(fn);
    }

    static removeListener(fn) {
        Logging.#listeners = Logging.#listeners.filter(f => f !== fn);
    }

    static #push(level, message, detail) {
        const entry = { level, message, detail, timestamp: Date.now() };
        Logging.#entries.push(entry);
        if (Logging.#entries.length > MAX_ENTRIES) {
            Logging.#entries.shift();
        }
        for (const fn of Logging.#listeners) fn(entry);
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
