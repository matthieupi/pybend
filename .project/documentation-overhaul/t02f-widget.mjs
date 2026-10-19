import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
const root = new URL('../../', import.meta.url).pathname;
const require = createRequire(`${root}/tests/frontend/package.json`);
const { JSDOM } = require('jsdom');
const dom = new JSDOM();
globalThis.document = dom.window.document;
const source = readFileSync(`${root}/packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js`, 'utf8');
const { Widget } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const text = readFileSync(`${root}/.opencode/skills/n3tx-widgets/SKILL.md`, 'utf8');
const snippet = text.match(/```javascript\n([\s\S]*?)```/)[1];
let widget;
new Function('Widget', 'registerWidget', snippet.replace(/^import .*;\n/gm, ''))(
  Widget, (name, instance) => { assert.equal(name, 'color'); widget = instance; }
);
for (const value of [null, '', 'blue', '<img src=x onerror=alert(1)>', '"<&']) {
  const expected = String(value ?? '');
  const display = widget.display(value, {}, {});
  assert.ok(display instanceof dom.window.Node);
  assert.equal(display.textContent, expected);
  const edit = widget.edit(value, {}, {}, () => {});
  assert.ok(edit instanceof dom.window.Node);
  // Mirror consumer operations without claiming a full Formidable execution.
  const editable = edit.querySelector('input, textarea, select') || edit;
  editable.dataset.key = 'color';
  const wrapper = document.createElement('div');
  wrapper.appendChild(edit);
  const mounted = document.createElement('div');
  mounted.innerHTML = wrapper.outerHTML;
  assert.equal(mounted.querySelector('input').value, expected);
  const list = document.createElement('div');
  list.innerHTML = widget.list(value, {}, {});
  assert.equal(list.textContent, expected);
  assert.equal(list.children.length, 0);
}
console.log('Extracted ColorWidget: 5 values passed Node/edit serialization/list escaping checks with actual Widget base + installed jsdom. Not a full Formidable/browser execution.');
