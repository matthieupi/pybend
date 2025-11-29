import assert from "../utils/Assert.js";
import { caution } from "../utils/Assert.js";

import Actor from './Actor.js';
import {NetworkAdapter} from "./transport/NetworkAdapter.js";
import Logging from "../utils/Logging.js";

export class Matrix extends Actor {
    
    
    constructor(url) {
        super(url);
        this.remote = new NetworkAdapter(this)
    }
    
    has(addr) {
        return this.children.has(addr.split('/')[0]);
    }
   
    inbox(event) {
        console.warn(`Matrix received event '${event.name}' for target: ${event.target}`, event);
        console.log(`Registered children:`, this.children);
        // Check if the target actor is local
        if (this.children.has(event.target)) {
            const actor = this.children.get(event.target);
            actor.inbox(event);
        }
        else if (this.children.has(event.target.split('/')[0])) {
            const actor = this.children.get(event.target.split('/')[0]);
            actor.inbox(event);
        } else {
            this.remote.send(event);
        }
    }
    
    dispatch(event) {
        this.inbox(event);
    }
    
    register(actor) {
        assert(this,  this.isActor(actor) , `Only Actor instances can be registered.`);
        caution(this, !this.children.has(actor.addr), `Actor with address ${actor.addr} is already registered.`);
        this.children.set(actor.addr, actor);
        Logging.debug(`[MATRIX] Registered actor at address:`, actor.addr);
    }
    
    isActor(actor) {
        if (actor instanceof Actor)
            return true;
        // Check if the object implements the Actor interface (addr, inbox)
        else if (actor && typeof actor.addr === 'string' && typeof actor.inbox === 'function')
            return true;
        else
            throw new Error(`Object ${actor} is not an Actor instance.`);
    }
    
}


export const matrix = new Matrix("matrix://root");