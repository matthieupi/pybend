import { Widget } from './Widget.js';

/**
 * CurrencyWidget — Renders monetary values.
 *
 * Migrated from existing inline currency handling in form.js.
 * Display: formatted $X,XXX.XX.
 * Edit: <input type="number"> with currency symbol prefix.
 * List: formatted number.
 */
export class CurrencyWidget extends Widget {

    display(value, config, schema) {
        const symbol = config?.symbol || '$';
        if (value == null || value === '') return document.createTextNode('');
        const formatted = typeof value === 'number'
            ? `${symbol}${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
            : `${symbol}${value}`;
        return this.el('span', { class: 'widget-currency' }, [formatted]);
    }

    edit(value, config, schema, onChange) {
        const symbol = config?.symbol || '$';
        const wrapper = document.createElement('div');
        wrapper.className = 'currency-input';

        const symbolSpan = document.createElement('span');
        symbolSpan.className = 'currency-symbol';
        symbolSpan.textContent = symbol;
        wrapper.appendChild(symbolSpan);

        const input = document.createElement('input');
        input.type = 'number';
        input.step = '0.01';
        input.setAttribute('value', value ?? '');
        if (onChange) input.addEventListener('input', () => {
            const num = parseFloat(input.value);
            onChange(isNaN(num) ? null : num);
        });
        wrapper.appendChild(input);
        return wrapper;
    }

    validate(value, config, schema) {
        if (value == null || value === '') return null;
        const num = parseFloat(value);
        if (isNaN(num)) return 'Please enter a valid number';
        if (schema?.minimum != null && num < schema.minimum)
            return `Must be at least ${schema.minimum}`;
        if (schema?.exclusiveMinimum != null && num <= schema.exclusiveMinimum)
            return `Must be greater than ${schema.exclusiveMinimum}`;
        if (schema?.maximum != null && num > schema.maximum)
            return `Must be at most ${schema.maximum}`;
        if (schema?.exclusiveMaximum != null && num >= schema.exclusiveMaximum)
            return `Must be less than ${schema.exclusiveMaximum}`;
        return null;
    }

    list(value, config, schema) {
        const symbol = config?.symbol || '$';
        if (value == null || value === '') return '';
        return typeof value === 'number'
            ? `${symbol}${value.toFixed(2)}`
            : `${symbol}${value}`;
    }
}
