/**
 * Widget Registry — Maps widget names to Widget instances.
 *
 * Usage:
 *   import { registerWidget, getWidgetForField } from './registry.js';
 *
 *   registerWidget('color', new ColorWidget());
 *
 *   const { widget, config } = getWidgetForField(fieldSchema);
 *   if (widget && fieldSchema.ui?.widget) {
 *       const node = widget.display(value, config, fieldSchema);
 *   }
 */

const _widgets = {};

/**
 * Register a widget instance by name.
 * @param {string} name - Widget identifier (matches ui.widget in schema)
 * @param {Widget} widgetInstance - Widget class instance
 */
export function registerWidget(name, widgetInstance) {
    _widgets[name] = widgetInstance;
}

/**
 * Look up the widget for a field schema.
 * @param {Object} fieldSchema - Field definition from JSON Schema
 * @returns {{ widget: Widget|null, config: Object }} Widget instance and config
 */
export function getWidgetForField(fieldSchema) {
    const ui = fieldSchema?.ui || {};
    const name = ui.widget;
    if (name && _widgets[name]) {
        return { widget: _widgets[name], config: ui.config || {}, name };
    }
    if (fieldSchema?.type === 'boolean' && _widgets.bool) {
        return { widget: _widgets.bool, config: {}, name: 'bool' };
    }
    if (fieldSchema?.['x-ref'] && _widgets.reference) {
        return {
            widget: _widgets.reference,
            config: { model: fieldSchema['x-ref'] },
            name: 'reference',
        };
    }
    return { widget: null, config: {}, name: null };
}

/**
 * Check if a widget is registered for the given name.
 * @param {string} name - Widget name
 * @returns {boolean}
 */
export function hasWidget(name) {
    return name in _widgets;
}
