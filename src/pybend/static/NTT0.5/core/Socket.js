import {default as logging} from "../utils/Logging.js"
//import Event from "../core/Event.js"


let DISCONNECTED = "DISCONNECTED"
let CONNECTED = "CONNECTED"
let CONNECTING = "CONNECTING"
let FAILED = "FAILED"
let PENDING = "PENDING"
let WAITING = "WAITING"
let RECONNECT = "RECONNECT"

const MAX_TRIES = 5

const eventTypes = {

}

/**
 * Handles event messages of the type:
 *
 * {
 *   "event": "event_name",
 *   "type": "event_type",
 *   "timestamp": "ISO_8601_timestamp",
 *   "source": "source_id_or_name",
 *   "target": "target_id_or_name",
 *   "data": {
 *     "key1": "value1",
 *     "key2": "value2",
 *     // Additional data fields
 *   },
 *   "meta": {
 *     "requestId": "unique_request_id",
 *     "priority": "high|medium|low"
 *   }
 * }
 */

/**
 * Class representing a websocket connection
 *

 * Sends a heartbeat every ttl milliseconds.
 * After two missed heartbeats, the Socket will reset and re-initiate the connection
 */
export default class Socket {

	static resources = {}
	static defaultSocket = undefined

    constructor(url, targets={}, ttl = 1000) {
		// 0. Init state
        this.url = url
		this.targets = targets
		this.listeners = targets
		this.state = "INITIAL"
		this.connection = undefined
		this.websocket = undefined
		this.lrh = Date.now() 				// Last received heartbeat
		this.ttl = ttl
		this.retries = 0
		this.isDisabled = true
		this.queue = []
		// 1. Bindings
		this.watchdog = this.watchdog.bind(this)
		this.onMessage = this.onMessage.bind(this)
		this.sendMessage = this.sendMessage.bind(this)
		this.heartbeat = this.heartbeat.bind(this)
		this.onOpen = this.onOpen.bind(this)
		this.onClose = this.onClose.bind(this)
		this.connect = this.connect.bind(this)
		this.disconnect = this.disconnect.bind(this)
		this.reconnect = this.reconnect.bind(this)
		this.disable = this.disable.bind(this)
		this.enable = this.enable.bind(this)
		this.dispatchEvent = this.dispatchEvent.bind(this)

		// 2. Log
		Socket.register(url, this)
		// 3. Connect and set watchdog
		this.connect(url)
		Socket.defaultSocket = this
    }

	/* ---------------------------- */
	/*     STAY ALIVE FUNCTIONS     */
	/* ---------------------------- */
	/**
	 *  Resets the time of the last received heartbeat (lrh) and sends a heartbeat
	 *
	 * @param {string} [msg=true] - The message to include in the heartbeat
	 */
	heartbeat(msg=true){
		this.lrh = Date.now()
		this.sendMessage("heartbeat", msg)
	}

	/**
	 * Run this function to verify and update the state of the connection
	 * with the distant machine
	 *
	 * States transitions are:
	 * [CONNECTING] -> [WAITING], [CONNECTED] -> [WAITING],
	 * [CONNECTING] -> [CONNECTED], [CONNECTED] -> [WAITING]
	 * [FAILED] -> reconnect(), [WAITING] -> reconnect()
	 *
	 */
	watchdog() {
		let elapsed = Date.now() - this.lrh
		// 1. If connecting, set to WAITING
		if (this.state === CONNECTING || this.state === RECONNECT){
			logging.warn("Socket", "CONNECTING")
			this.state = WAITING
			this.heartbeat()
		}
		// If connection faslied, try to reconnect
		else if (this.state === FAILED){
			logging.error("Socket", "socket failed")
			this.reconnect()
		}
		// If client was already waiting and ttl is up, try to reconnect
		else if (this.state === WAITING && elapsed > 3*this.ttl){
			this.disable()
			this.disconnect()
			// 1.1 Reset socket
			logging.error("Socket", "Socket is disconnected. Will close the socket")
			this.interval = setInterval(()=> {
				logging.error("Socket", "try to reconnect after disconnection")
				this.reconnect()	
			} , 1000);
			
		}
		// If ttl is up, set to WAITING
		else if (elapsed > this.ttl) {
			this.sendMessage("heartbeat", false)
			this.state = WAITING
			logging.debug("Watchdog updated state, elapsed time: " +elapsed, WAITING)
			elapsed = Date.now()
		}
		// Update interface
		if (this.state === CONNECTED){
			this.enable()
		}
	}
	
	disable() {
		const event = new SocketEvent("DISABLE", "DISABLE", this.url, "*", {disable: true})
		// Disable interface
		if (!this.isDisabled) {
			for (let key in this.targets){
				this.targets[key](event)
			}
		}
		// Update state
		this.isDisabled = true
	}
	
	enable() {
		// Enable interface
		if (this.isDisabled) {
			for (let key in this.targets){
				this.targets[key](new SocketEvent("ENABLE", "ENABLE", this.url, "*", {enable: true}))
			}
		}
		// Update state
		this.isDisabled = false
	}

	/* ---------------------------- */
	/*    CONNECTIVITY FUNCTIONS    */
	/* ---------------------------- */
	/**
	 * Connects the object to the distant machine at "url" via this.websocket
	 *
	 * @param url
	 * @returns {Socket}
	 */
	connect(url, callback=()=>{}){
		console.info("Connecting websocket: ws://" + url);
		this.websocket = undefined
		this.state = CONNECTING
		this.connectCallback = callback

		try {
			this.websocket = new WebSocket("ws://" + url);
			this.websocket.onopen = this.onOpen;
			this.websocket.onclose = this.onClose;
			this.websocket.onmessage = this.onMessage;
			this.websocket.onerror = function(event) {
									let reconnectButton = `<button onclick="()=>connectTo('${url}')" class='btn center reconnect'>Reconnection</button>`;
									//window.error("WebSocket error observed");
								};
		} catch (e) {
			logging.error("Erreur sur le websocket: ", e);
			this.state = FAILED
		}

		return this
	}

	/**
	 * Reconnects websocket on timeout
	 *
	 * Keeps the interval, closes the websocket and reopens a new one
	 */
	reconnect(){
		if (this.retries > MAX_TRIES)
			this.disconnect()
		else {
			this.retries += 1
			if (this.websocket)
				this.websocket.close()
			this.connect(this.url, this.connectCallback)
			this.state = RECONNECT
		}
	}

	/**
	 * Close connection and clean up socket
	 */
	disconnect(){
		if (this.websocket.readystate === 1) {
			websocket.close()
		}
		if (this.interval) {
			clearInterval(this.interval)
			this.interval = undefined
		}
		logging.dev("Websocket successfully disconnected")
		this.state = DISCONNECTED
		this.retries = 0
	}

	/**
	 * Register a created socket in the Socket.resources registry
	 * @param {string} name - The event type
	 * @param {Socket} socket - The name to register the socket under
	 */
	static register(name, socket){
		if (Socket.resources[name])
			logging.warn("Socket", "Overwriting resource in registration")
		Socket.resources[name] = socket
	}


	/**
	 * Unregister a socket from the Socket.resources
	 * @param {string} name - The name of the socket to remove
	 */
	static unregister(name) {
		Socket.resources[name].disconnect()
		delete Socket.resources[name]
	}


	/**
	 * Register a target for this socket
	 * @param {string} event - The event type
	 * @param {string} target - The name or unique id to register the callback under
	 * @param {Socket} callback - The socket to be registered
	 */
	 setTarget(target, callback){
		 console.log("Setting target", target, callback)
		// If targets already exist, add warn
		if (Socket.resources[target]) {
			logging.warn("Socket 278", "Overwriting resource in registration")
		}
		// If event does not exist, create it
		this.targets[target] = callback
		return this
	}


	/**
	 * Unregister a target from the socket.targets
	 * @param {string} event
	 * @param {string} target
	 * @returns {Socket}
	 */
	removeTarget(id ) {
		delete this.targets[id]
		return this
	}

	dispatchEvent(event){
		if (!this.targets.hasOwnProperty(event.target)) {
			logging.error("Socket 323:", `No target in socket for:  ${event.target}: ${event.name}`)
		} else if (this.targets[event.target]){
			this.targets[event.target](event)
		}
	}

	/* ------------------------------------------ */
	/*              Websocket functions           */
	/* ------------------------------------------ */

	/**
	 * Function parsing and dispatching messages
	 * @param msg
	 */
	onMessage(msg){
		let data = {}
		// The socket is confirmed connected once a message is received
		if (this.state !== CONNECTED) {
			this.state = CONNECTED
		}
		// Extract and dispatch event
		try {
			data = JSON.parse(msg.data)
		} catch (e) {
			logging.error("Unable to parse socket MSG to json\n", e)
			return
		}
		if (!data.hasOwnProperty("heartbeat")) {
			logging.debug("SOCKET RECEIVED:\n ",msg.data)
			const event = SocketEvent.fromString(msg.data)
			this.dispatchEvent(event)
		}
		else {
			this.heartbeat()
			logging.debug("SOCKET HEARTBEAT:      ", "PROCESSED")
		}
		// If there are messages in the queue, send them now that the socket is connected
		//this.queue.map((msg, i)=>setTimeout(this.sendMessage(msg.key, msg.msg), i*5 ))
		if (this.queue.length > 0) {
			for (let i = 0; i < this.queue.length; i++) {
				// Copy str to variable
				console.warn("Sending queued message")
				console.warn(this.queue[i])
				const queueMsg = JSON.parse(JSON.stringify(this.queue[i]))
				// Iteratively send messages
				setTimeout(() => this.sendMessage(undefined, queueMsg), i * 5)
			}
			this.queue = []
		}

		// Update last received heartbeat
		this.lrh = Date.now()
	}

	/**
	 * Post information on client socket
	 * @param key - The name of the client function
	 * @param msg - Params for the client
	 * @param plain - Send as is without stringifying it
	 */
	sendMessage(key, msg, plain=false) {
		// 1. Prepare data to be sent
		let data = {}
		if (key) {
			data[key] = msg
		} else {
			data = msg
		}
		// 2. If not connected, cue the message
		if (this.websocket.readyState !== 1){
			this.queue.push(data)
			logging.debug("Cueing message", data)
			//this.websocket.send(JSON.stringify({heartbeat: true}))
			return
		}
		// If not heartbeat, show data
		if (key !== "heartbeat"){
			logging.debug("359: SOCKET SENDING:\n", data)
		}
		//this.websocket.send("{\"heartbeat\": \"heartbeat\"})
		//this.websocket.send(JSON.stringify({...data}))
		if (plain) {
			this.websocket.send(msg)
		} else{
			this.websocket.send(JSON.stringify(data))
		}
		return this
	}

	/**
	 * Send an event

	 * @param {SocketEvent} event
	 */
	sendEvent(event){
		this.websocket.send(event.toString())
	}


	/**
	 * Function running when a websocket is opened
	 *
	 * Currently only logs to dev
	 * @param event
	 */
	onOpen(event) {
		if (this.websocket.readyState == 1){
			// Code to execute after ws is ready goes here
		}
		this.state = CONNECTING
		if (this.interval)
			clearInterval(this.interval)
		this.interval = window.setInterval(this.watchdog, this.ttl)
		this.heartbeat()
		window.success("Websocket connection established")
		this.connectCallback()
		this.sendMessage("allStatesRequest", true);
	}

	/**
	 *
	 * Function running when a websocket is closed
	 * @param event
	 */
	onClose(event) {
		//if (event.target.url === window.url)
		let msg = "Websocket connection closed"
		logging.warn('Connection closed', event);
		
		
		this.disable()

		if (event.code == 1000){
			window.warn("Websocket closed normally \n" + event)
		} else {
			console.warn(this.state)
			console.error("Websocket closed abnormally with code "+ event.code )
		}
		this.state = DISCONNECTED
	}


}

window.WS = Socket
