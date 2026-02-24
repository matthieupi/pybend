import assert from "../utils/Assert.js";
import { caution } from "../utils/Assert.js";

import Actor from './Actor.js';
import {NetworkAdapter} from "./transport/NetworkAdapter.js";
import Logging from "../utils/Logging.js";
import TX from "./TX.js";
import {config} from "../config.js"
const E = config.E;

export class Matrix extends Actor {
    
    constructor(addr, url="") {
        super(addr);
        // When initializing the first Matrix, register it as the root actor
        if (!Actor.root){
            Actor.registerRoot(this);
        }
        this.remote = new NetworkAdapter(this, url)
    }
    
    has(addr) {
        return this.children.has(addr.split('/')[0]);
    }
   
    inbox(event) {
        let tx = event instanceof TX ? event : new TX(event);
        //console.warn(`Matrix received event '${event.name}' for target: ${event.target}`, event);
        //console.log(`[MATRIX] Inbox received event '${event.source}' for target: ${event.target}`);
        Logging.event(tx);

        let targetAddr = tx.target.split('/')[0];
        // Check if the target actor is local
        if (tx.name === E.connect){
            tx = this.connect(tx.source, tx.target);
        } else if (tx.target === this.addr) {
            throw new Error(`Matrix cannot send messages to itself at address ${this.addr}.`);
        } else if (this.children.has(targetAddr)) {
            // Forward to local child actor
            //console.log(`[MATRIX] Forwarding event '${tx.name}' to local actor at address:`, targetAddr)
            //tx.target = tx.target.replace(`${targetAddr}`, '').replace(/^\/+/,''); // Remove the processed prefix
            Logging.dev(`[MATRIX] Forwarding '${tx.name}' to ${targetAddr}`)
            tx = this.children.get(targetAddr).inbox(tx.repr())
        } else {
            tx = this.remote.send(tx);
        }
        return tx;
    }
    
    dispatch(event) {
        this.inbox(event);
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
    
}


// Required initialization step for all Actor Classes
Actor.subclass(Matrix)
// Create the ROOT matrix instance
export const matrix = new Matrix("matrix://root");
