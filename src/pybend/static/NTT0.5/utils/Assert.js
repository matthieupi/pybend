
class AssertionError extends Error {
    constructor(message) {
        super(message);
        this.name = 'AssertionError';
    }
}

export default function assert(caller, condition, message) {
    if (!condition)
        //throw new AssertionError(`\n${caller}\n${message || ''}`);
        if (!!caller)
            throw new AssertionError(`${caller.name}\n${message || ''}`);
        else
            throw new AssertionError(`${message || ''}`);
};

/**
 * assert(1 === 1); // Executes without problem
 * assert(false, 'Expected true');
 * Yields 'Error: Assert failed: Expected true' in console
 */