
Object.defineProperty( Date.prototype,
    'toStringDM', {value:
            (date) => {
                return date.getDate() + '-' + date.getMonth();
            }
    });

Object.defineProperty( Date.prototype,
    'toStringDMY', {value:
            (date) => {
                return date.getDate() + '-' + date.getMonth() +'-' + date.getFullYear();
            }
    });

Object.defineProperty(Date.prototype, 'timeNow', {value: getCurrentTime})

export function getCurrentTime() {
  let now = new Date();
  let hour = now.getHours();
  let minute = now.getMinutes();
  if (minute < 10)
      minute = "0" + minute
  if (hour < 10)
      hour = "0" + hour
  return hour + ":" + minute;
}