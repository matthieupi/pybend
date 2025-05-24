export class NTT {
  #name;
  #addr;
  #href;
  #data;
  #schema;
  #prototype;
  #meta;

  static #registry = new Map();
  static #prototypes = new Map();
  
  static handler = {};

  constructor({ name, addr, href = null, data = {}, prototype = {}, meta = {} }) {
    if (!name || !addr) throw new Error('Ntt requires at least a name and address');

    this.#name = name;
    this.#addr = addr;
    this.#href = href || addr;
    this.#data = { ...data };
    this.#meta = { ...meta };

    if (typeof prototype === 'string') {
      this.resolveAndPromote(prototype);
    } else if (prototype instanceof NTT) {
      this.#prototype= prototype;
    } else if (typeof prototype === 'object') {
      // TODO if a type descriptor is passed, promote it to it's own class
      // this.#prototype = this.prototypeFromSchema(prototype);
      // For now we simply copy the object
      this.#prototype = { ...prototype };
    } else {
      throw new TypeError('prototype must be an object or a URL string');
    }
  }

  // ------------------ Getters & Setters ------------------

  get name() { return this.#name; }
  set name(val) { this.#name = val; }

  get addr() { return this.#addr; }
  set addr(val) { this.#addr = val; }

  get href() { return this.#href; }
  set href(val) { this.#href = val; }

  get data() { return { ...this.#data }; }
  set data(val) {
    if (typeof val !== 'object') throw new TypeError('data must be an object');
    this.#data = { ...this.#data, ...val };
  }

  get prototype() { return { ...this.#prototype }; }
  set prototype(val) {
    if (typeof val === 'string') {
      let promise = this.resolveAndPromote(val);
    } else if (typeof val === 'object') {
      this.#prototype = { ...val };
    } else {
      throw new TypeError('prototype must be an object or a URL string');
    }
  }

  get meta() { return { ...this.#meta }; }
  set meta(val) {
    if (typeof val !== 'object') throw new TypeError('meta must be an object');
    this.#meta = { ...this.#meta, ...val };
  }

  // ------------------ Dynamic Promotion ------------------

  async resolveAndPromote(url) {
    if (NTT.#registry.has(url)) {
      const ProtoClass = NTT.#prototypes.get(url);
      const instance = NTT.#registry.get(url);
      Object.setPrototypeOf(this, ProtoClass.prototype);
      this.#prototype = ProtoClass.prototype;
      return this;
    }

    try {
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error(`Failed to fetch prototype from ${url}`);
      const schema = await res.json();

      const Subclass = NTT.generateSubclass(schema);
      NTT.#registry.set(url, Subclass);
      Object.setPrototypeOf(this, Subclass.prototype);
      this.#prototype = schema;
    } catch (err) {
      console.error(`[Ntt] Failed to resolve and promote prototype from ${url}`, err);
      this.#prototype = {};
    }
  }

  // ------------------ Dynamic Class Generator ------------------

  static generateSubclass(schema, className = null) {
    const fields = Object.keys(schema.properties || {});
    const classTitle = className || schema.title || 'DynamicNtt';

    const Subclass = class extends NTT {
      constructor(opts) {
        super(opts);
      }
    };

    for (const field of fields) {
      const definition = schema.properties[field];
      const isReadonly = definition.readOnly === true;
      const label = definition.title || field;
      const hidden = definition.extra && definition.extra.hidden;

      Object.defineProperty(Subclass.prototype, field, {
        get() {
          return this.data[field];
        },
        set(value) {
          if (isReadonly) {
            throw new Error(`Field '${field}' is read-only`);
          }

          const expectedType = definition.type;
          if (expectedType && !NTT.#isTypeCompatible(value, expectedType)) {
            throw new TypeError(`Invalid type for '${field}': expected ${expectedType}`);
          }

          this.data = { [field]: value }; // triggers partial merge
        },
        enumerable: !hidden,
        configurable: true,
      });

      // Optionally store label in metadata
      if (!Subclass.labels) Subclass.labels = {};
      Subclass.labels[field] = label;
    }

    Object.defineProperty(Subclass, 'name', { value: classTitle });

    return Subclass;
  }

  // ------------------ Type Checking ------------------

  static #isTypeCompatible(value, expectedType) {
    const jsType = typeof value;
    switch (expectedType) {
      case 'string': return jsType === 'string';
      case 'number': return jsType === 'number';
      case 'integer': return Number.isInteger(value);
      case 'boolean': return jsType === 'boolean';
      case 'object': return value && jsType === 'object' && !Array.isArray(value);
      case 'array': return Array.isArray(value);
      default: return true; // fallback: accept anything
    }
  }

  // ------------------ Utilities ------------------

  toJSON() {
    return {
      name: this.#name,
      addr: this.#addr,
      href: this.#href,
      data: this.#data,
      prototype: this.#prototype,
      meta: this.#meta,
    };
  }

  clone() {
    const Ctor = Object.getPrototypeOf(this).constructor;
    return new Ctor({
      name: this.#name,
      addr: this.#addr,
      href: this.#href,
      data: structuredClone(this.#data),
      prototype: structuredClone(this.#prototype),
      meta: structuredClone(this.#meta),
    });
  }

  static getRegisteredSubclass(url) {
    return NTT.#registry.get(url);
  }

  static clearRegistry() {
    NTT.#registry.clear();
  }
}
