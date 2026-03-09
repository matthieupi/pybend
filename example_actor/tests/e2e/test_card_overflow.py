"""Tests: card CSS must prevent content overflow.

Verifies that ntx-item.css and ntx-method.js contain the CSS rules needed
to prevent card content (inputs, comments, method fields) from overflowing
the card container.

These are framework-level CSS tests that check the source of truth directly.
"""
import os
import re

# Paths to the framework CSS/JS files
_STATIC = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src', 'n3tx', 'static')
ITEM_CSS = os.path.join(_STATIC, 'components', 'ntx-item.css')
METHOD_JS = os.path.join(_STATIC, 'components', 'ntx-method.js')
STREAM_JS = os.path.join(_STATIC, 'components', 'ntx-stream.js')


def _read(path):
    with open(path) as f:
        return f.read()


def _strip_comments(css):
    """Remove CSS block comments."""
    return re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)


def test_card_md_has_overflow_hidden():
    """The .card[data-display="md"] rule must set overflow:hidden.

    Without this, child elements (nested comments, method fieldsets,
    stream outputs) can visually bleed past the card's rounded borders.
    """
    css = _strip_comments(_read(ITEM_CSS))

    # Find the .card[data-display="md"] block
    match = re.search(
        r'\.card\[data-display="md"\]\s*\{([^}]+)\}',
        css,
    )
    assert match, "Could not find .card[data-display='md'] rule in ntx-item.css"
    block = match.group(1)

    assert 'overflow' in block, (
        f'.card[data-display="md"] has no overflow property. '
        f'Content can visually overflow the card boundary. '
        f'Block contents:\n{block}'
    )
    # Must be overflow: hidden (not visible, not auto)
    overflow_match = re.search(r'overflow\s*:\s*(\w+)', block)
    assert overflow_match and overflow_match.group(1) == 'hidden', (
        f'.card[data-display="md"] overflow is "{overflow_match.group(1) if overflow_match else "missing"}", '
        f'expected "hidden"'
    )


def test_card_lg_has_overflow_hidden():
    """The .card[data-display="lg"] rule must set overflow:hidden."""
    css = _strip_comments(_read(ITEM_CSS))

    match = re.search(
        r'\.card\[data-display="lg"\]\s*\{([^}]+)\}',
        css,
    )
    assert match, "Could not find .card[data-display='lg'] rule in ntx-item.css"
    block = match.group(1)

    assert 'overflow' in block, (
        f'.card[data-display="lg"] has no overflow property. '
        f'Block contents:\n{block}'
    )


def test_card_xl_has_overflow_hidden():
    """The .card[data-display="xl"] rule must set overflow:hidden."""
    css = _strip_comments(_read(ITEM_CSS))

    match = re.search(
        r'\.card\[data-display="xl"\]\s*\{([^}]+)\}',
        css,
    )
    assert match, "Could not find .card[data-display='xl'] rule in ntx-item.css"
    block = match.group(1)

    assert 'overflow' in block, (
        f'.card[data-display="xl"] has no overflow property. '
        f'Block contents:\n{block}'
    )


def test_ntx_item_inputs_have_box_sizing():
    """input, textarea in ntx-item.css must use box-sizing: border-box.

    Without this, width:100% + padding causes the input to exceed
    the card container width, creating horizontal overflow.
    """
    css = _strip_comments(_read(ITEM_CSS))

    # Find the shared input, textarea rule
    match = re.search(
        r'(?:^|\n)\s*input\s*,\s*textarea\s*\{([^}]+)\}',
        css,
    )
    assert match, "Could not find shared 'input, textarea' rule in ntx-item.css"
    block = match.group(1)

    assert 'box-sizing' in block, (
        f'ntx-item.css "input, textarea" rule has no box-sizing property. '
        f'width:100% + padding exceeds container. '
        f'Block contents:\n{block}'
    )
    bs_match = re.search(r'box-sizing\s*:\s*([\w-]+)', block)
    assert bs_match and bs_match.group(1) == 'border-box', (
        f'ntx-item.css input box-sizing is "{bs_match.group(1) if bs_match else "missing"}", '
        f'expected "border-box"'
    )


def test_ntx_method_inputs_have_box_sizing():
    """ntx-method.js baseStyles input must use box-sizing: border-box.

    The method component renders inputs inside shadow DOM with its own
    styles. Without box-sizing, width:100% + padding causes overflow
    within the parent card.
    """
    js = _read(METHOD_JS)

    # Find the baseStyles static property
    match = re.search(r'baseStyles\s*=\s*`([^`]+)`', js, re.DOTALL)
    assert match, "Could not find baseStyles template literal in ntx-method.js"
    styles = match.group(1)

    # Find the input rule within baseStyles
    input_match = re.search(r'input\s*\{([^}]+)\}', styles)
    assert input_match, "Could not find 'input' rule in ntx-method baseStyles"
    block = input_match.group(1)

    assert 'box-sizing' in block, (
        f'ntx-method.js baseStyles input has no box-sizing property. '
        f'width:100% + padding causes the input to overflow the parent card. '
        f'Block contents:\n{block}'
    )


def test_ntx_item_host_has_min_width_zero():
    """:host must set min-width: 0 for grid overflow prevention.

    In a CSS Grid context (ntx-list uses grid), items default to
    min-width:auto which allows content to expand the column.
    Setting min-width:0 on :host ensures the card respects grid
    column boundaries.
    """
    css = _strip_comments(_read(ITEM_CSS))

    # Find the :host { } rule (not :host([display=...]) variants)
    match = re.search(
        r':host\s*\{([^}]+)\}',
        css,
    )
    assert match, "Could not find :host rule in ntx-item.css"
    block = match.group(1)

    assert 'min-width' in block, (
        f'ntx-item.css :host rule has no min-width property. '
        f'Grid items with min-width:auto can overflow their column. '
        f'Block contents:\n{block}'
    )


if __name__ == '__main__':
    test_card_md_has_overflow_hidden()
    test_card_lg_has_overflow_hidden()
    test_card_xl_has_overflow_hidden()
    test_ntx_item_inputs_have_box_sizing()
    test_ntx_method_inputs_have_box_sizing()
    test_ntx_item_host_has_min_width_zero()
    print("All tests passed!")
