/**
 * Widget System — Public entry point.
 *
 * Imports all built-in widgets, registers them, and re-exports the public API.
 *
 * Usage:
 *   import { Widget, registerWidget, getWidgetForField } from '../widgets/index.js';
 *
 * App developer extension:
 *   import { Widget, registerWidget } from '../widgets/index.js';
 *
 *   class ColorWidget extends Widget {
 *       display(value) { ... }
 *       edit(value, config, schema, onChange) { ... }
 *   }
 *   registerWidget('color', new ColorWidget());
 */

export { Widget } from './Widget.js';
export { registerWidget, getWidgetForField, hasWidget } from './registry.js';

import { registerWidget } from './registry.js';
import { UrlWidget } from './UrlWidget.js';
import { EmailWidget } from './EmailWidget.js';
import { DateWidget } from './DateWidget.js';
import { MarkdownWidget } from './MarkdownWidget.js';
import { ConsoleWidget } from './ConsoleWidget.js';
import { ReferenceWidget } from './ReferenceWidget.js';
import { CurrencyWidget } from './CurrencyWidget.js';
import { TextareaWidget } from './TextareaWidget.js';
import { BoolWidget } from './BoolWidget.js';
import { ListFieldWidget } from './ListFieldWidget.js';

// ── Register built-in widgets ──────────────────────────────────────
registerWidget('url', new UrlWidget());
registerWidget('email', new EmailWidget());
registerWidget('date', new DateWidget());
registerWidget('datetime', new DateWidget());   // DateWidget handles both
registerWidget('markdown', new MarkdownWidget());
registerWidget('console', new ConsoleWidget());
registerWidget('reference', new ReferenceWidget());
registerWidget('currency', new CurrencyWidget());
registerWidget('textarea', new TextareaWidget());
registerWidget('bool', new BoolWidget());
registerWidget('list', new ListFieldWidget());
