/**
 * NTTElement — Single entity base class.
 *
 * Handles the data lifecycle for one entity instance:
 *   - Receives data via UPDATE, DESCRIBE, READ message handlers
 *   - Provides save() to push changes back to the backend
 *   - Auto-renders when value changes and schema is available
 *
 * Subclass and override render() to build custom entity components.
 * The built-in NTTItem (ntt-item.js) provides a zero-config default.
 */
import {Component} from '../core/Component.js';
import {NTT} from '../core/NTT.js';
import Logging from '../utils/Logging.js';
import assert from '../utils/Assert.js';
import TX from '../core/TX.js';


export class NTTElement extends Component {

  // Track the schema name for CONNECT flow
  $schema = undefined;

  constructor() {
    super({});  // Default value: single entity object
  }

  /** ─────────────────────────────────────────── **/
  /**         Value Override (auto-render)          **/
  /** ─────────────────────────────────────────── **/

  set value(data) {
    const prev = super.value;
    super.value = data;
    // Auto-render when we have both schema and data
    if (this.schema && this.schema.__name__) {
      if (!this.update(prev, data)) {
        this.render();
      }
    }
  }
  get value() { return super.value; }

  /** Surgical DOM update. Override in subclasses. Returns false → full render(). */
  update(prev, next) { return false; }


  /** ─────────────────────────────────────────── **/
  /**         Message Handlers                     **/
  /** ─────────────────────────────────────────── **/

  /**
   * Receives entity data push (e.g. from DynamicClass watcher notification,
   * or from another component sending an UPDATE).
   */
  UPDATE(data) {
    Logging.dev(`[NTTElement] ${this.schema.__name__} — UPDATE`, data);
    assert(this, "$schema" in data, "UPDATE data missing $schema field");
    this.value = data;

    // If the schema source changed, send CONNECT to resolve it
    const schemaName = data['$schema']?.split('/').pop();
    if (this.$schema !== schemaName) {
      this.$schema = schemaName;
      this.send(new TX({
        name: 'CONNECT',
        source: this.addr,
        target: this.$schema
      }));
    }
  }

  /**
   * Receives proto + data together (from NTT instance ATTACH response).
   * Also subscribes to the NTT entity's signal so future value changes
   * (e.g. after pull()) automatically re-render this component.
   */
  DESCRIBE(data) {
    Logging.dev(`[NTTElement ${this.model}] — DESCRIBE`, data);
    this.schema = data.proto;
    this.value = data.data;   // value setter auto-renders when schema is available

    // Subscribe to entity signal for live updates
    const id = data.data?.id;
    const model = data.proto?.__name__;
    if (model && id !== undefined) {
      const entity = NTT.get(`${model}/${id}`);
      if (entity?.signal) {
        this._entityUnsub?.();
        this._entityUnsub = entity.signal((ent) => {
          if (ent.value) this.value = ent.value;
        }, true);  // wait=true: don't fire immediately, DESCRIBE already set value
      }
    }
  }

  /**
   * Receives data from a direct URL fetch (ListRef href resolution).
   */
  READ(data) {
    const modelName = this.getAttribute('data-model');
    const DynClass = modelName ? NTT.get(modelName) : null;
    if (DynClass) {
      this.schema = DynClass._schema;
      this.value = data;  // value setter handles render via update() fallback
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Save                                 **/
  /** ─────────────────────────────────────────── **/

  /**
   * Sends the current value as an UPDATE TX back to the entity's ref.
   * Call this from your component when the user commits edits.
   */
  save() {
    this.send(new TX({
      name: 'UPDATE',
      source: this.addr,
      target: this.ref,
      data: this.value
    }));
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._entityUnsub?.();
  }
}
