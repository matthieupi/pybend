
export default class Logging {
    static log(val1, val2) {
        let caller = log.caller().name
        console.log(val1, val2, caller)
    }
   static dev(val1, val2) {
       console.log(val1, val2)
   }

    static debug(val1, val2) {
        console.info(val1, val2)
    }

   static warn(val1, val2) {
       if (val2)
           console.warn(val1, val2)
       else
           console.warn(val1)
   }

   static error(val1, val2) {
       if (!val2)
           console.error("Logging error:", val1)
       else
           console.error(val1, val2)
       //console.error(val2)
   }
}