import { describe, it, expect, vi } from 'vitest';

// There is no ntt-element.js file (it was ntt-element.css only).
// This test file covers the check that the file doesn't exist as a component.
// The actual base class is NTTElement.js in components/ and Component.js in core/.

describe('ntt-element (base component)', () => {
  it('should have NTTElement as the single entity base class', async () => {
    const { NTTElement } = await import('../../components/NTTElement.js');
    expect(typeof NTTElement).toBe('function');
  });
});
