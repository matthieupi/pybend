/**
 * NTTUser — User entity component with avatar rendering.
 *
 * Overrides xs/sm from NTTItem to show circular avatar images
 * instead of generic pill/row layouts. Uses value.image when
 * available, falls back to ui-avatars.com.
 *
 * md/lg/xl inherited from NTTItem unchanged.
 */
import {NTTItem} from './ntx-item.js';


export class NTTUser extends NTTItem {

  get styles() { return new URL('./ntx-user.css', import.meta.url).href; }

  /** Private: resolve avatar image URL. */
  #avatarUrl() {
    if (this.value?.image) return this.value.image;
    const name = this.value?.name || 'User';
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=1a2332&color=5eeadf&size=56&bold=true`;
  }

  /** xs — Circular avatar only. */
  xs() {
    const url = this.#avatarUrl();
    return `<img class="user-avatar" src="${url}" alt="" />`;
  }

  /** sm — Avatar + name. */
  sm() {
    const url = this.#avatarUrl();
    const name = this.value?.name
      || (this.value?.email ? this.value.email.split('@')[0] : null)
      || 'User';
    return `
      <img class="user-avatar" src="${url}" alt="" />
      <span class="sm-name">${name}</span>
    `;
  }
}

customElements.define('ntx-user', NTTUser);
