/**
 * NTTFavorites — Favorites page component.
 *
 * Mounted by ntt-router when navigating to #@favorites.
 * Wraps an ntt-list for the ProductLike collection route.
 */
class NTTFavorites extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <ntt-list model="ProductLike" display="md"></ntt-list>
    `;
  }
}

customElements.define('ntt-favorites', NTTFavorites);
