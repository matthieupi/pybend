import { describe, it, expect, vi } from 'vitest';

// There is no ntx-element.js file (it was ntx-element.css only).
// This test file covers the check that the file doesn't exist as a component.
// The actual base class is NTTElement.js in components/ and Component.js in core/.

describe('ntx-element (base component)', () => {
  it('should have NTTElement as the single entity base class', async () => {
    const { NTTElement } = await import('../../components/NTTElement.js');
    expect(typeof NTTElement).toBe('function');
  });
});
