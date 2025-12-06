// core/Observable.js
import Actor from "./Actor.js";
import assert from "../utils/Assert.js";

/**
 * Observable mixin for Actors.
 *
 * Usage:
 *   Actor.subclass(MyClass, Observable)
 *
 * This will mutate MyClass.prototype to include:
 *   - signal(callback?, wait?)
 *   - observe(property, callback)
 *   - notify(property, newValue, oldValue)
 *
 * It stores data on the instance (no private fields),
 * so it works for any Actor subclass without changing its
 * constructor signature.
 */
export default class Observable extends Actor {

  /**
   * Apply this mixin to a given Actor subclass.
   * This function MUTATES the Base class (prototype and optionally static),
   * and returns it for convenience.
   *
   * @param {Function} Base - The class to augment (e.g. Component, TT, Product, ...)
   * @returns {Function} The same Base class, augmented.
   */
  static apply(Base) {
    if (typeof Base !== "function") {
      throw new TypeError(`[Observable] Base must be a class (function), got: ${Base}`);
    }

    const proto = Base.prototype;

    // Avoid overriding if already present
    if (!Object.prototype.hasOwnProperty.call(proto, "_initObservable")) {
      Object.defineProperty(proto, "_initObservable", {
        configurable: true,
        enumerable: false,
        writable: true,
        value: function _initObservable() {
          if (!this.__signals) this.__signals = new Set();
          if (!this.__observers) this.__observers = new Map();
        },
      });
    }

    if (!Object.prototype.hasOwnProperty.call(proto, "signal")) {
      Object.defineProperty(proto, "signal", {
        configurable: true,
        enumerable: false,
        writable: true,
        value: function signal(callback = undefined, wait = false) {
          this._initObservable();

          assert(this, !callback || typeof callback === "function",
            `[Observable] Callback must be a function if given.`);

          if (callback) {
            if (!wait) {
              // When wait is false, immediately call the callback
              callback(this);
            }
            // Add the callback to the signals set
            this.__signals.add(callback);
            // Return an unsubscribe function
            return () => { this.__signals.delete(callback); };
          } else {
            // When called with no callback, signal to all listeners
            this.__signals.forEach(cb => cb(this));
          }
        },
      });
    }

    if (!Object.prototype.hasOwnProperty.call(proto, "observe")) {
      Object.defineProperty(proto, "observe", {
        configurable: true,
        enumerable: false,
        writable: true,
        value: function observe(property, callback) {
          this._initObservable();

          assert(this,
            property && typeof property === "string",
            `[Observable] Property must be a non-empty string.`);
          assert(this,
            callback && typeof callback === "function",
            `[Observable] Callback must be a function.`);

          if (!this.__observers.has(property)) {
            this.__observers.set(property, new Set());
          }
          this.__observers.get(property).add(callback);

          // Unsubscribe function
          return () => {
            const set = this.__observers.get(property);
            if (!set) return;
            set.delete(callback);
            if (set.size === 0) {
              this.__observers.delete(property);
            }
          };
        },
      });
    }

    if (!Object.prototype.hasOwnProperty.call(proto, "notify")) {
      Object.defineProperty(proto, "notify", {
        configurable: true,
        enumerable: false,
        writable: true,
        value: function notify(property, newValue, oldValue) {
          this._initObservable();

          assert(this,
            property && typeof property === "string",
            `[Observable] Property must be a non-empty string.`);

          const set = this.__observers && this.__observers.get(property);
          if (!set) return;

          set.forEach(cb => cb(newValue, oldValue, property, this));
        },
      });
    }

    return Base;
  }
}
