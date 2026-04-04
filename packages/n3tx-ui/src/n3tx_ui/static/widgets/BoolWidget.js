import { Widget } from './Widget.js';

export class BoolWidget extends Widget {
    display(value) {
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.className = 'widget-bool widget-bool--readonly';
        const checked = !!value;
        input.checked = checked;
        input.toggleAttribute('checked', checked);
        input.tabIndex = -1;
        input.setAttribute('aria-disabled', 'true');
        input.setAttribute('aria-label', value ? 'True' : 'False');
        return input;
    }

    edit(value, config, schema, onChange) {
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.className = 'widget-bool';
        const checked = !!value;
        input.checked = checked;
        input.toggleAttribute('checked', checked);
        if (onChange) input.addEventListener('change', () => onChange(input.checked));
        return input;
    }

    list(value) {
        return `<input type="checkbox" class="widget-bool" disabled ${value ? 'checked' : ''}>`;
    }
}
