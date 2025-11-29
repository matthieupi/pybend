import {config} from '../config.js';
export default class Logging {
    static log(val1, val2) {
        if (config.LOGGING < 3) return;
        // let caller = log.caller().name
        // console.log(val1, val2, caller)
        console.log(`[${new Date().toISOString()}]`, val1, val2);
    }
   static dev(val1, val2) {
        if (config.LOGGING < 4) return;
         console.log(val1, val2)
   }

    static debug(val1, val2) {
        if (config.LOGGING < 5) return;
        console.info(val1, val2)
    }

   static warn(val1, val2) {
        if (config.LOGGING < 2) return;
       if (val2)
           console.warn(val1, val2)
       else
           console.warn(val1)
   }

   static error(val1, val2) {
         if (config.LOGGING < 1) return;
       if (!val2)
           console.error("Logging error:", val1)
       else
           console.error(val1, val2)
       //console.error(val2)
   }
}