import assert from "../utils/Assert.js";
import Socket from "../Socket.js";
import {TransportManager} from "./TransportManager.js";

const E = {
	"ENABLE": "ENABLE",
	"DISABLE": "DISABLE",
	"UPDATE": "UPDATE",
	"GET": "GET",
	"DESCRIBE": "DESCRIBE",
	"CONNECTED": "CONNECTED"

}
export default class Event {

	transport = new TransportManager()

	constructor(name, id, source, target, data={}, meta={}, timestamp=Date.now()) {
		this.name = name
		this.id = id ? id : Math.random().toString(36).substring(7)
		this.source = source
		this.target = target
		this.tst = timestamp
		this.data = data
		this.meta = meta

		assert(this,typeof(this.name) === "string", `Event name must be a string, got ${typeof this.name}\n${this.name}`)
		assert(this,typeof(this.id) === "string", `Event id must be a string, got ${id} with type ${typeof this.id}`)
		assert(this, typeof(this.source) === "string", `Source must be a string, got ${typeof this.source}\n${this.source}`)
		assert(this, typeof(this.target) === "string", `Target must be a string, got ${typeof this.target}\n${this.target}`)
		assert(this, typeof(this.meta) === "object", `Meta must be an object, got ${typeof this.meta}\n${this.meta}`)

		this.dispatch = this.dispatch.bind(this)
		this.repr = this.repr.bind(this)
	}

	dispatch() {
		assert(this, !!this.transport, "window.TransportManager not set. Cannot dispatch event.")
		console.info(`Dispatching event ${this.name} from ${this.source} to ${this.target}`, this.repr())
		this.transport.send("event", this.repr())
	}

	repr() {
		const obj = {}
		obj.name = this.name
		obj.id = this.id
		obj.source = this.source
		obj.target = this.target
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
