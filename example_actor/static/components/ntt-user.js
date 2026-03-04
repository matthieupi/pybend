/**
 * NTTUser — User entity component.
 *
 * Extends NTTItem, overriding only xs and sm for user-specific rendering:
 *   xs — Circle avatar (image or letter initial)
 *   sm — Circle avatar + name
 *
 * All other sizes (md, lg, xl) inherit from NTTItem unchanged.
 * Demonstrates selective extensibility with minimal code.
 */
import { NTTItem } from './ntt-item.js';

export class NTTUser extends NTTItem {

  get styles() { return new URL('./ntt-user.css', import.meta.url).href; }

  /** Generate a letter-initial avatar URL as fallback. */
  #avatarUrl() {
    const img = this.value.image;
    if (img) return img;
    const name = encodeURIComponent(this.value.name || this.value.email || '?');
    return `https://ui-avatars.com/api/?name=${name}&background=1a9e94&color=fff&size=64&rounded=true`;
  }

  /** xs — Circle avatar only (no text). */
  xs() {
    return `<img class="user-avatar" src="${this.#avatarUrl()}" alt="" />`;
  }

  /** sm — Circle avatar + name. */
  sm() {
    const name = this.value.name || this.value.email?.split('@')[0] || 'User';
    return `
      <img class="user-avatar" src="${this.#avatarUrl()}" alt="" />
      <span class="sm-name">${name}</span>
    `;
  }
}

customElements.define('ntt-user', NTTUser);
