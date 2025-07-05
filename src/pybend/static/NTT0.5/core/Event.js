import assert from "../utils/Assert.js";
import {simpleHash} from "./Utils.js";
import {dispatch, registry} from "./registrar.js";

export default class Event {

	static #transport = window.Remote

	constructor({name, source, target, data={}, meta={}, timestamp=Date.now()}) {
		this.name = name
		this.source = source
		this.target = target
		this.data = data
		this.meta = meta
		this.tst = timestamp
		this.hash = simpleHash(this.repr())
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
		dispatch(this.target, this.repr())
	}

	repr() {
		const obj = {}
		obj.name = this.name
		obj.source = this.addr
		obj.target = this.href
		obj.data = this.data
		obj.meta = this.meta
		obj.hash = this.hash
		obj.tst = this.tst
		return obj
	}

	static fromString(str) {
		let obj = JSON.parse(str)
		return new Event(
			obj.name,
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

class ReadEvent extends Event {
	constructor(source, target) {
		super(E.READ, source, target)
	}
}

export {
	Event,
	ReadEvent,
}
