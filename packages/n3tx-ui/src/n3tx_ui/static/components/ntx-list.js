/**
 * NTTList — Built-in default collection component.
 *
 * Provides zero-config rendering for any model collection.
 * Stamps <ntx-item> per entity by default.
 *
 * For custom list rendering, extend ListElement directly instead.
 */
import './ntx-item.js';
import {ListElement} from './ListElement.js';


export class NTTList extends ListElement {

  get styles() { return new URL('./ntx-list.css', import.meta.url).href; }

}

customElements.define('ntx-list', NTTList);
