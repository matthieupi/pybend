import assert from "../utils/Assert.js";
import {simpleHash} from "./Utils.js";
import {config} from "../config.js";

export const E = config.E;

export default class TX {
	
	
	/**
	 * Create a new TX (transaction) event.
	 *
	 * @param event {Object|string} - The event object or its JSON string representation. If it is a string, it will be
	 * parsed as JSON.
	 *
	 */
	constructor(event) {
		// If event is a string, parse it as JSON
		if (typeof event === 'string') {
			event = JSON.parse(event)
		}
		// Destructure event properties with defaults
		let {name, source, target, data={}, meta={}, timestamp=Date.now()} = event
		// Instantiate properties
		this.name = name
		this.source = source
		this.target = target
		this.data = data
		this.meta = meta
		this.tst = timestamp
		this.hash = simpleHash(this.repr())
	}

	/**
	 * Dispatch the event through the transport layer.
	 *
	 * @throws {AssertError} If the transport manager is not set.
	dispatch() {
		console.info(`Dispatching event ${this.name} from ${this.addr} to ${this.href}`, this.repr())
		dispatch(this.target, this.repr())
	}
	 */
	repr() {
		const obj = {}
		obj.name = this.name
		obj.source = this.source
		obj.target = this.target
		obj.data = this.data
		obj.meta = this.meta
		obj.hash = this.hash
		obj.tst = this.tst
		return obj
	}
	
	str() {
		return JSON.stringify(this.repr())
	}

	static fromString(str) {
		let obj = JSON.parse(str)
		return new TX({
			name: obj.name,
			id: obj.id,
			source: obj.source,
			target: obj.target,
			data: obj.data,
			meta: obj.meta || {},
			timestamp: obj.timestamp || Date.now()
		})
	}

}

class ConnectEvent extends TX {
	constructor(source, target) {
		super({name: E.CONNECT, source: source, target: target})
	}
}


class EnableEvent extends TX {
    constructor(source, target) {
        super({name: E.ENABLE, source, target}, )
    }
}

class DisableEvent extends TX {
    constructor(source, target) {
        super(E.DISABLE, "", source, target)
    }
}

class UpdateEvent extends TX {
    constructor(source, target, data) {
        super(E.UPDATE, "", source, target, data)
    }
}

class GetEvent extends TX {
    constructor(source, target) {
        super(E.GET, source, target)
    }
}

class DescribeEvent extends TX {
    constructor(source, target) {
        super(E.DESCRIBE, source, target)
    }
}

class ReadEvent extends TX {
	constructor(source, target) {
		super(E.READ, source, target)
	}
}

export {
	TX,
	ConnectEvent,
	ReadEvent,
}
