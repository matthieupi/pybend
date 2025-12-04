import {config} from '../config.js';
export default class Logging {
    
    static log(val1, val2) {
        if (config.LOGGING < 3) return;
        val1 = Logging.pad(val1)
        // let caller = log.caller().name
        // console.log(val1, val2, caller)
        console.log(`[${new Date().toISOString()}]`, val1, val2);
    }
   static dev(val1, val2) {
        if (config.LOGGING < 4) return;
        val1 = Logging.pad(val1)
        // Rewrite the log to add fixed padding to aliign mukltiple val1 lengths and val2
        // 2. Print the true caller location as a separate entry
        let caller = _getCaller();

        console.log(
            "%c" + val1 + "%c" + val2 + "%c" + caller,
            "color: gray; font-weight: bold;",                                  // val1
            "color: inherit; font-weight: bolder;",                            // val2
            "display:inline-block; text-align:right; color:#888; float:right" // right column
        );
   }
   
   static event(val1, val2) {
        if (!config.LOGEVENTS) return;
        this.warn(val1, val2)
   }

    static debug(val1, val2) {
        if (!config.DEBUG) return;
        val1 = Logging.pad(val1)
        let caller = _getCaller();
        console.info(
            "%c" + val1 + "%c" + val2 + "%c" + caller,
            "color: gray; font-weight: bold;",                                  // val1
            "color: inherit; font-weight: bolder;",                            // val2
            "display:inline-block; text-align:right; color:#888; float:right" // right column
        );
    }

   static warn(val1, val2="") {
       if (config.LOGGING < 2) return;
       val1 = Logging.pad(val1)
       let caller = _getCaller()
       if (val2)
           console.warn(
               "%c" + val1 + "%c" + val2 + "%c" + caller,
               "color: gray; font-weight: bold;",                                  // val1
               "color: inherit; font-weight: bolder;",                            // val2
               "display:inline-block; text-align:right; color:#888; float:right" // right column
           );
   }

   static error(val1, val2) {
       if (config.LOGGING < 1) return;
       val1 = Logging.pad(val1)
       let caller = _getCaller()
       if (!val2)
           console.error("Logging error:", val1)
       else
           console.error(
               "%c" + val1 + "%c" + val2 + "%c" + caller,
               "color: gray; font-weight: bold;",                      // val1
               "color: inherit; font-weight: bolder;",                // val2
               "display:inline-block; text-align:right; color:#888; float:right" // right column
           );
       //console.error(val2)
   }
   
   static pad(val1, length=55) {
        return String(val1).padEnd(length, " ");
   }
}


function _getCaller() {
    const stack = new Error().stack.split("\n");

    // stack[0] = Error
    // stack[1] = Logging.log()
    // stack[2] = actual caller (we want this one)


    // stack[2] is the caller of Logging.log()
    let raw = stack[2] || stack[1];

    raw = raw.trim().replace(/^at\s+/, "");

    // Example input:
    // Actor@http://localhost:63342/pystack/NTT0.6/core/Actor.js:14:17

    // Extract function name + file
    const match = raw.match(/^(.*?)@.*\/([^\/]+:\d+:\d+)/);

    if (!match) return raw;   // fallback

    const funcName = match[1].trim();
    const file = match[2];

    return `${funcName} @ ${file}`;
}