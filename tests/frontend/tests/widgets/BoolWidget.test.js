import { describe, it, expect } from 'vitest';

import { BoolWidget } from '../../widgets/BoolWidget.js';

describe('BoolWidget', () => {
  it('serializes a checked display checkbox for true values', () => {
    const widget = new BoolWidget();
    const wrapper = document.createElement('div');
    wrapper.appendChild(widget.display(true));

    const html = wrapper.innerHTML;

    expect(html).toContain('type="checkbox"');
    expect(html).toContain('widget-bool');
    expect(html).toContain('checked');
    expect(html).not.toContain('disabled=""');
    expect(html).toContain('aria-disabled="true"');
  });

  it('serializes a checked edit checkbox for true values', () => {
    const widget = new BoolWidget();
    const wrapper = document.createElement('div');
    wrapper.appendChild(widget.edit(true));

    const html = wrapper.innerHTML;

    expect(html).toContain('type="checkbox"');
    expect(html).toContain('widget-bool');
    expect(html).toContain('checked');
  });
});
