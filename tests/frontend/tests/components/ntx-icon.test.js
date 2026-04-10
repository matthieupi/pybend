import { describe, it, expect } from 'vitest';

import '../../components/ntx-icon.js';

describe('ntx-icon.js', () => {
  it('renders emoji values with monochrome emoji styling', () => {
    const el = document.createElement('ntx-icon');
    el.setAttribute('value', '📚');
    document.body.appendChild(el);

    const emoji = el.shadowRoot.querySelector('.icon--emoji');
    expect(emoji).not.toBeNull();
    expect(emoji.textContent).toBe('📚');

    document.body.removeChild(el);
  });

  it('renders lookup keys through the shared registry', () => {
    const el = document.createElement('ntx-icon');
    el.setAttribute('value', 'star');
    document.body.appendChild(el);

    const html = el.shadowRoot.innerHTML;
    expect(html).toContain('icon--svg');
    expect(html).toContain('<polygon');

    document.body.removeChild(el);
  });

  it('renders URL values as images', () => {
    const el = document.createElement('ntx-icon');
    el.setAttribute('value', '/static/icons/books.svg');
    document.body.appendChild(el);

    const image = el.shadowRoot.querySelector('.icon--image');
    expect(image).not.toBeNull();
    expect(image.getAttribute('src')).toBe('/static/icons/books.svg');

    document.body.removeChild(el);
  });

  it('degrades unknown lookup keys to text', () => {
    const el = document.createElement('ntx-icon');
    el.setAttribute('value', 'books');
    document.body.appendChild(el);

    const text = el.shadowRoot.querySelector('.icon--text');
    expect(text).not.toBeNull();
    expect(text.textContent).toBe('books');

    document.body.removeChild(el);
  });
});
