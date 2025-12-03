import assert from "../utils/Assert.js";
import { caution } from "../utils/Assert.js";

import Actor from './Actor.js';
import {NetworkAdapter} from "./transport/NetworkAdapter.js";
import Logging from "../utils/Logging.js";
import TX from "./TX.js";
import {config} from "../config.js"
const E = config.E;

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
        let tx = event instanceof TX ? event : new TX(event);

        let targetAddr = tx.target.split('/')[0];
        // Check if the target actor is local
        if (tx.name === E.connect){
            tx = this.connect(tx.source, tx.target);
        } else if (tx.target === this.addr) {
            throw new Error(`Matrix cannot send messages to itself at address ${this.addr}.`);
        } else if (this.children.has(targetAddr)) {
            tx = this.children.get(targetAddr).inbox(tx.repr())
        } else {
            tx = this.remote.send(tx);
        }
        return tx;
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
    
    connect(source, target) {
        // The target is in the form of /ChildrenClass/child-addr
        // Lets parse it to extract the claas
        const [sourceClass, ...sourceAddrRemainder] = source.split('/').filter(part => part);
        const [targetClass, ...targetAddrRemainder] = target.split('/').filter(part => part);
        if (this.children.has(targetClass)) {
            let tx = this.children.get(targetClass).inbox(new TX({name: E.connect, source: source, target: target}).repr());
            return tx;
        } else {
            // Get the actor from the remote
            // Source from outside the matrix
            // Todo: Analalyze if we need to handle network init for a class here (vs should be done externally
            //       by registration)
            // target = `${config.API_URL}/${target}`
            // this.network.send(new TX({name: E.SCHEMA, source: source, target: target}).repr());
            throw new Error(`Cannot connect to target actor class ${targetClass} as it is not registered locally in the Matrix.`);
        }
        
    }
    
    isActor(actor) {
        if (actor instanceof Actor)
            return true;
        // Check if the object implements the Actor interface (addr, inbox)
        else if (actor && typeof actor.addr === 'string' && typeof actor.inbox === 'function')
            return true;
        else
            console.warn(actor)
        // TODO Whty is actor.addr showing up as undefined here?
        // There is a getter in Component hierarchy that should make this work
        console.log(actor.addr, typeof actor.inbox)
            throw new Error(`Object ${actor} is not an Actor instance.`);
    }
    
}


export const matrix = new Matrix("matrix://root");