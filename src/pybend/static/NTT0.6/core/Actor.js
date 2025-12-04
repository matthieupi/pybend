/**
 *  Actor Model inspired by Akka.js
 */
import assert from "../utils/Assert.js";
import Logging from "../utils/Logging.js";
import TX from "./TX.js";

let ROOT_ACTOR = null; // Will be set by Matrix


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
        this.#parent = this.constructor
        this.#children = new Map(); // Child actors
        console.warn(this)
        this.constructor.register(this); // Register in type-level children map
        // Bindings
        this.inbox = this.inbox.bind(this);
        this.send = this.send.bind(this);
        
    }
    
     /**
       * Register the top-level root Actor (Matrix) so static send() can route via it.
       */
    static registerRoot(actor) {
        assert(this, !ROOT_ACTOR, `ROOT_ACTOR cannot be changed once registered.`)
        ROOT_ACTOR = actor;
    }

    static get root() {
        return ROOT_ACTOR;
    }
     
     /**
     * Default type-level address for a class actor is its constructor name.
     * Subclasses can override.
     */
    static get addr() {
        return this.name;
    }
    
        /**
     * Generic static send routing:
     *  - If the target is one of this type’s local children, route directly.
     *  - If the target is prefixed with this type (e.g. "/Component/child-addr"),
     *    strip the prefix and route to the child.
     *  - Otherwise, bubble the message up to the root Matrix, prefixing the source
     *    with this type’s address.
     */
    static _send(event) {
        // Normalize to TX
        let tx = event instanceof TX ? event : new TX(event);
        // Ensure the system is properly INIT
        if (!ROOT_ACTOR) {
            throw new Error(
                `No root actor registered. Make sure an Actor calls Actor.registerRoot(this) during the system's initialization.`
            );
        }
        // Local initialization
        console.warn(`[Actor.${this.addr}_send] Routing message to target: ${tx.target}`, this.children)
        const Type = this; // the concrete subclass (e.g. Component)
        const children = Type.children; // Subclasses must expose a static children map
        const typeAddr = Type.addr || Type.name;
        const sourcePrefix = `/${typeAddr}`;
        const rawTarget = tx.target || "";
        const [targetParent, targetChild] = rawTarget
            .split("/")
            .filter(Boolean); // removes empty segments
        // Routing logic
        // Case 1: target is directly one of our children (by addr)
        if (children && children.has(targetParent)) {
            children.get(targetParent).inbox(tx.repr());
        }
        // Case 2: target looks like "/this.addr/child-addr" and we own that child
        else if (targetParent === this.addr) {
            if (children && targetChild && children.has(targetChild)) {
                console.log("Forwarding message to child actor at address:", targetChild)
                tx.target = rawTarget.replace(sourcePrefix, "");
                tx.target = rawTarget.replace(typeAddr, "");
                children.get(targetChild).inbox(tx.repr());
            } else {
                throw new Error(
                    `[Actor.${this.addr}_send] Cannot route message to target: ${tx.target}. No such child actor.`
                );
            
            }
        }
        // Case 3: we don’t recognize the target – bubble it in the system's hierarchy
        else {
            tx.source = tx.source ? `${typeAddr}/${tx.source}` : typeAddr;
            
             // Traverse the class (constructor) hierarchy
            let ParentType = Object.getPrototypeOf(Type);

            /* Temporarily disabled parent delegation, all goes through the matrix
            // While we haven’t reached plain Function.prototype…
            while (ParentType && ParentType.name) {

                // If parent defines an inbox, delegate to it
                if (typeof ParentType.inbox === "function") {
                    return ParentType.inbox(tx.repr());
                }

                // Climb further up the inheritance chain
                ParentType = Object.getPrototypeOf(ParentType);
            }
            */

            // No parent type handled it → bubble to root Matrix
            return ROOT_ACTOR.inbox(tx.repr())
            
        }

        return tx;
    }
    
    static _inbox(event) {
        console.warn(`[Actor.${this.addr}_inbox] Received message for target: ${event.target}`)
        const tx = event instanceof TX ? event : new TX(event);
        const Type = this;
        const Prototype = Object.getPrototypeOf(this);
        if (tx.target === `/${Type.addr}` || tx.target === Type.addr) {
            console.log(`[${this.addr}._inbox] Handling message for self:`, tx)
            console.log(this)
            console.log(Object.getOwnPropertyNames(this))
            // Check if has method
            if (this.hasOwnProperty(tx.name)) {
                return this[tx.name](tx.data);
            } else if(Prototype.hasOwnProperty(tx.name)){
                return Prototype[tx.name].call(this, tx.data);
            } else {
                throw new Error(`[${this.addr}._inbox] No handler for event ${tx.name}.`);
            }
        } else {
          Type.send(event)
        }
        return tx;
    }
    
    
       /**
     * Helper for instance registration into the type-level children map.
     * Call this from the base-class constructor (e.g. Component's constructor).
     */
    static _register(actor) {
        // 1. When caller context is a class, register actor in its parent type's children map
        if (typeof this === "function"){
            assert(this, actor, `[Actor.register] Actor to register must be provided when called from a Class`)
            assert(this, actor instanceof this,
                `[Actor.register] Only ${this.name} instances can be registered in ${this.name}, got ${actor.name}`)
        // 2. When caller context is an instance, register in its type's children map
        } else if (this instanceof Actor)  {
        // 3. What are you trying to do?
        } else {
            throw new Error(`[Actor.register] What are you trying to register, a Giraffe?: ${this}`)
        }
           console.log(parent, actor)
        this.children.set(actor.addr, actor);
        
        /*
           
        // If actor is instance, register in its type's children map
        if (actor instanceof Actor)
            this._children.set(actor.addr, actor);
        console.error(`[Actor.register] Registering instance of ${actor.constructor.name} at addr: ${actor.addr}`)
           console.log(actor)
           console.log(this)
        const Type = actor.constructor;

        if (typeof actor.addr !== "string" || !actor.addr) {
            Logging.warn(
                `[Actor.registerChild] Instance of ${Type.name} has no valid 'addr' string; not added to children map.`
            );
            return;
        }

        Type._children.set(actor.addr, actor);
        
         */
    }
    
      /**
     * "Metaclass" helper:
     *  - Adds static addr / children / send
     *  - Adds a default instance send that delegates to the static one
     */
    static subclass(ChildClass=undefined, { addr } = {}) {
        // TODO: Make callable via ChildClass.subclass()
        // if (this.name && !this.name === "Actor"){
        //     ChildClass = this;
        // }
        
        // Make sure ChildClass is a class
        assert(this, typeof ChildClass === "function", `Actor.subclass: ChildClass must be a class.`)
        if (!ChildClass) {
            throw new Error(`Actor.subclass: ChildClass must be provided.`);
        }
        const Type = ChildClass;
        // Idempotent – do nothing if already done
        if (Type.__isActor) {
            console.warn(`Actor.subclass: Type ${Type.name} is already an Actor subclass.`)
            return Type;
        }
        // ------------- STATIC CLASS ATTRIBUTE SETUP -------------- //
        if (!Object.getOwnPropertyDescriptor(Type, "addr")) {
            Object.defineProperty(Type, "addr", {
                configurable: true,
                get() {
                    return addr || Type.name;
                },
            });
        }
        if (!Object.getOwnPropertyDescriptor(Type, "_children")) {
            Object.defineProperty(Type, "_children", {
                value: new Map(),
                writable: false,
                configurable: false,
            });
        }
        if (!Object.getOwnPropertyDescriptor(Type, "children")) {
            Object.defineProperty(Type, "children", {
                configurable: true,
                get() {
                    return Type._children;
                },
            });
        }
        // ------------- STATIC CLASS METHOD SETUP -------------- //
        Type.send = function (event) {
            return Actor._send.call(Type, event);
        };
        Type.inbox = function (event) {
            const tx = event instanceof TX ? event : new TX(event);
            return Actor._inbox.call(Type, tx);
        };
        Type.register = function (actor) {
            return Actor._register.call(Type, actor);
        }
        // Register to parent class children map
        const ParentType = Object.getPrototypeOf(Type);
        // TODO ths can easily execute with another Type before the Matrix is setup. Enhance by checking for Matrix type?
        if (ROOT_ACTOR)
            ROOT_ACTOR.register(Type);
        /**
        if (ParentType && ParentType.register) {
            console.log(`[Actor.subclass] Registering ${Type.name} in parent ${ParentType.name}`)
            ParentType.register(Type);
        }
         */
        // ------------- INSTANCE ATTRIBUTE SETUP -------------- //
        const childrenDescriptor = Object.getOwnPropertyDescriptor(Type.prototype, "_children");
        if (!childrenDescriptor || childrenDescriptor.value === Actor.prototype._children) {
            console.log(`[Actor.subclass] Setting up instance _children map for ${Type.name}`)
            Type.prototype._children = new Map();
            // Children getter and setter
            Object.defineProperty(Type.prototype, "children", {
                configurable: true,
                get() {
                    return this._children;
                },
            });
        }
        // ------------- INSTANCE METHOD SETUP -------------- //
        const sendDescriptor = Object.getOwnPropertyDescriptor(Type.prototype, "send");
        if (!sendDescriptor || sendDescriptor.value === Actor.prototype.send) {
            Type.prototype.send = function (event) {
                return this.constructor.send(event);
            };
        }
        /**
        const registerDescriptor = Object.getOwnPropertyDescriptor(Type.prototype, "send");
        if (!registerDescriptor || registerDescriptor.value === Actor.prototype.send) {
            Type.prototype.register = function (event) {
                return this.constructor._register(event);
            };
        }
        */

        // Mark as augmented
        Object.defineProperty(Type, "__TypeActor", {
            value: true,
            writable: false,
            configurable: false,
        });

        return Type;
    }
    
    get addr() {
        return this.#addr;
    }
    
    get children() {
        return this.#children;
    }
    
    inbox(event) {
        return Actor._inbox.call(this, event);
    }
    
    register(actor) {
        Actor._register.call(this, actor);
    }
    
    static isActor(obj) {
        return obj instanceof Actor || (obj && obj.__TypeActor === true);
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