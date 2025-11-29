import {config} from "../config.js";

class AssertionError extends Error {
    constructor(message) {
        super(message);
        this.name = 'AssertionError';
    }
}

export default function assert(caller, condition, message, trigger='error') {
    if (!condition)
        //throw new AssertionError(`\n${caller}\n${message || ''}`);
        if (trigger === 'error'){
            if (!!caller)
                throw new AssertionError(caller ? `[${caller.name}] Assertion error: ${message}` : "", `\n${message || ''}`);
            else
                throw new AssertionError(`${message || ''}`);
        } else if (trigger === 'warn') {
            console.warn(`${caller ? `[${caller.name}]` : ''} Assertion warning\n    ${message || ''}`);
        } else if (trigger === 'info') {
            console.info(`${caller ? `[${caller.name}]` : ''} Assertion info\n    ${message || ''}`);
        } else {
        }
};

export function caution(caller, condition, message) {
    if (config.LOGGING < 2) return;
    assert(caller, condition, message, 'warn');
}

export function inform(caller, condition, message) {
    if (config.LOGGING < 4) return;
    assert(caller, condition, message, 'info');
}


/**
 * assert(1 === 1); // Executes without problem
 * assert(false, 'Expected true');
 * Yields 'Error: Assert failed: Expected true' in console
 */