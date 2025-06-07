import assert from "../utils/Assert.js";
import NTT from "./NTT.js";

const E = {
	// UI Events
	"ENABLE": "ENABLE",
	"DISABLE": "DISABLE",
	"DESCRIBE": "DESCRIBE",
	"CONNECTED": "CONNECTED",
	"DISCONNECTED": "DISCONNECTED",
	// CRUD operations
	"CREATE": "CREATE",
	"READ": "READ",
	"UPDATE": "UPDATE",
	"DELETE": "DELETE",
	"GET": "GET",
	// STATE management
	"EVOLVE": "EVOLVE",
	"COMMIT": "COMMIT",
	"ROLLBACK": "ROLLBACK",
	"SUBSCRIBE": "SUBSCRIBE",
	"OBSERVE": "OBSERVE",

}
export default class Event extends NTT{

	static #transport = window.Remote

	constructor({name, addr, href, data={}, meta={}, timestamp=Date.now()}) {
		super({name, addr, href, data, meta})
		this.tst = timestamp
		//this.dispatch = this.dispatch.bind(this)
		//this.repr = this.repr.bind(this)
	}

	/**
	 * Dispatch the event through the transport layer.
	 *
	 * @throws {AssertError} If the transport manager is not set.
	 */
	dispatch() {
		assert(this, !!Event.#transport, "window.remote not set. Cannot dispatch event.")
		console.info(`Dispatching event ${this.name} from ${this.addr} to ${this.href}`, this.repr())
		Event.#transport.send(this.repr())
	}

	repr() {
		const obj = {}
		obj.name = this.name
		obj.id = this.id
		obj.source = this.addr
		obj.target = this.href
		obj.data = this.data
		obj.meta = this.meta
		obj.tst = this.tst
		return obj
	}

	static fromString(str) {
		let obj = JSON.parse(str)
		return new Event( obj.name,
								obj.id,
								obj.source,
								obj.target,
								obj.data,
								obj.meta || {},
								obj.timestamp || Date.now())
	}

}


class EnableEvent extends Event {
    constructor(source, target) {
        super(E.ENABLE, source, target)
    }
}

class DisableEvent extends Event {
    constructor(source, target) {
        super(E.DISABLE, "", source, target)
    }
}

class UpdateEvent extends Event {
    constructor(source, target, data) {
        super(E.UPDATE, "", source, target, data)
    }
}

class GetEvent extends Event {
    constructor(source, target) {
        super(E.GET, source, target)
    }
}

class DescribeEvent extends Event {
    constructor(source, target) {
        super(E.DESCRIBE, source, target)
    }
}

class ConnectedEvent extends Event {
	constructor(source, id) {
		super(E.CONNECTED, id || "", source, source)
	}
}

export {E, Event, ConnectedEvent, EnableEvent, DisableEvent, UpdateEvent }
