/**
 * NTTFavorites — Favorites page component.
 *
 * Mounted by ntx-router when navigating to #@favorites.
 * Wraps an ntx-list for the ProductLike collection route.
 */
class NTTFavorites extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <ntx-list model="ProductLike" display="md"></ntx-list>
    `;
  }
}

customElements.define('ntx-favorites', NTTFavorites);
