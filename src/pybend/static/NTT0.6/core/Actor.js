/**
 *  Actor Model inspired by Akka.js
 */
import assert from "../utils/Assert.js";
import Logging from "../utils/Logging.js";
import TX from "./TX.js";


export default class Actor {
    
    #addr;
    #children;
    
    constructor(addr = "", send = undefined) {
        Logging.dev(`Initializing Actor at address:`,`${addr}`)
        // Address generation
        if (!addr) {
            addr = `actor-${Math.random().toString(36).substr(2, 9)}`;
        }
        // Instantiation
        this.#addr = addr
        this.#children = new Map(); // Child actors
        // Bindings
        this.inbox = this.inbox.bind(this);
        this.send = this.send.bind(this);
        
    }
    
    static send(event) {
        throw new Error("Static Send method must be implemented in subclass.");
    }
    
    get addr() {
        return this.#addr;
    }
    
    get children() {
        return this.#children;
    }
    
    inbox(event) {
        if (typeof event === 'string') {
            event = Actor.parseEvent(event)
        }
        else if (typeof event == 'object') {
            event = TX(...event)
        }
    }
    
    send(event) {
        throw new Error("Send method must be implemented in subclass.");
    }
    
    spawn(addr, ActorClass, ...args) {
        assert(this, !this.#children.has(addr), `Child actor with address ${addr} already exists.`);
        if (!ActorClass) {
            ActorClass = Actor; // Default to base Actor class
        }
        const child = new ActorClass(addr, ...args);
        this.#children.set(addr, child);
        console.info(`Spawned child actor at address: ${addr}`);
        return child;
    }
    
}