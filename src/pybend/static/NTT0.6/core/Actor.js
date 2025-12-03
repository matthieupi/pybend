/**
 *  Actor Model inspired by Akka.js
 */
import assert from "../utils/Assert.js";
import Logging from "../utils/Logging.js";
import TX from "./TX.js";



export default class Actor {
    
    #addr;
    #parent;
    #children;
    
    constructor(addr = "") {
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
      // TODO : Implement static send method here instead of in child classes. The send method is currently  found in
      //   Component but needs to be adapted to work generically for all Actor subclasses. This is an issue due to the fact
      //   That different levels have different #children maps. Effectively, what we are trying to achieve is a way to
      //   route messages through the Actor hierarchy, starting from the root (Matrix) down to the target Actor.
      //   In order to do this, we want to make the Types, or children classes, actors themselves.
    }
    
    get addr() {
        return this.#addr;
    }
    
    get children() {
        return this.#children;
    }
    
    inbox(event) {
        const tx = event instanceof TX ? event : new TX(event);
        return tx;
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