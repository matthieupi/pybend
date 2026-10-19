import { describe, it, expect } from 'vitest';

import { ReferenceWidget } from '../../widgets/ReferenceWidget.js';

describe('ReferenceWidget', () => {
  const ref = 'https://storage.example.com/api/v1/File/file-12';
  const schema = { type: 'string', format: 'uri', 'x-ref': 'File' };

  it('renders an absolute entity URL without inventing a hash path', () => {
    const widget = new ReferenceWidget();
    const link = widget.display(ref, { model: 'File' }, schema);

    expect(link.getAttribute('href')).toBe(ref);
    expect(link.getAttribute('data-ref-model')).toBe('File');
    expect(link.textContent).toBe('File #file-12');
  });

  it('edits the complete URL rather than a local id', () => {
    const widget = new ReferenceWidget();
    const input = widget.edit(ref, { model: 'File' }, schema);

    expect(input.type).toBe('url');
    expect(input.value).toBe(ref);
    expect(input.placeholder).toContain('File URL');
  });
});
