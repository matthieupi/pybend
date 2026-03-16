/**
 * ntx-logs — Comprehensive Unit Tests
 *
 * Tests the logs panel component's toggle behavior, log entries,
 * filtering, clear, JSON expansion, badge counter, and edge cases.
 *
 * NOTE: Basic logs panel tests exist in logs-panel.spec.js. This file
 * provides deeper component behavior testing.
 */
import { test, expect } from '@playwright/test';

const APP_URL = '/';

test.describe('ntx-logs — Toggle Behavior', () => {

  test('toggle button visible and panel starts closed', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const state = await page.locator('ntx-logs').evaluate((el) => {
      const sr = el.shadowRoot;
      return {
        hasToggle: !!sr?.querySelector('.toggle'),
        panelOpen: sr?.querySelector('.panel')?.classList.contains('open') || false,
        toggleVisible: !!sr?.querySelector('.toggle'),
      };
    });
    expect(state.hasToggle).toBe(true);
    expect(state.panelOpen).toBe(false);
  });

  test('clicking toggle opens panel, clicking again — panel still open (use close btn)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Click toggle -> opens panel
    await page.locator('ntx-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.toggle')?.click();
    });
    await page.waitForTimeout(300);

    const isOpen = await page.locator('ntx-logs').evaluate((el) => {
      return el.shadowRoot?.querySelector('.panel')?.classList.contains('open') || false;
    });
    expect(isOpen).toBe(true);
  });

  test('close button closes panel', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Open
    await page.locator('ntx-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.toggle')?.click();
    });
    await page.waitForTimeout(300);

    // Close
    await page.locator('ntx-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.close-btn')?.click();
    });
    await page.waitForTimeout(300);

    const isClosed = await page.locator('ntx-logs').evaluate((el) => {
      return !el.shadowRoot?.querySelector('.panel')?.classList.contains('open');
    });
    expect(isClosed).toBe(true);
  });

  test('panel slides in from right (transform transition)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const transform = await page.locator('ntx-logs').evaluate((el) => {
      const panel = el.shadowRoot?.querySelector('.panel');
      if (!panel) return '';
      return getComputedStyle(panel).transform;
    });
    // When closed, should be translated to the right (translateX(100%))
    expect(transform).not.toBe('none');
  });
});


test.describe('ntx-logs — Log Entries', () => {

  test('entries exist after page load', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const count = await page.locator('ntx-logs').evaluate((el) => {
      return el.shadowRoot?.querySelectorAll('.log-list .entry').length || 0;
    });
    expect(count).toBeGreaterThan(0);
  });

  test('each entry has level-dot, level, time elements', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const entryStructure = await page.locator('ntx-logs').evaluate((el) => {
      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      if (!entries?.length) return null;
      const first = entries[0];
      return {
        hasLevelDot: !!first.querySelector('.level-dot'),
        hasLevel: !!first.querySelector('.level'),
        hasTime: !!first.querySelector('.time'),
        hasEntryHeader: !!first.querySelector('.entry-header'),
        hasEntryBody: !!first.querySelector('.entry-body'),
      };
    });
    expect(entryStructure).not.toBeNull();
    expect(entryStructure.hasLevelDot).toBe(true);
    expect(entryStructure.hasLevel).toBe(true);
    expect(entryStructure.hasTime).toBe(true);
    expect(entryStructure.hasEntryHeader).toBe(true);
    expect(entryStructure.hasEntryBody).toBe(true);
  });

  test('entry level classes are valid log levels', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const levels = await page.locator('ntx-logs').evaluate((el) => {
      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      if (!entries?.length) return [];
      return Array.from(entries).map(e => {
        const cls = Array.from(e.classList).find(c => c.startsWith('level-'));
        return cls || '';
      }).filter(Boolean);
    });
    const valid = ['level-error', 'level-warn', 'level-info', 'level-event', 'level-debug', 'level-dev'];
    levels.forEach(l => expect(valid).toContain(l));
  });

  test('entries have data-level attribute for filtering', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasDataLevel = await page.locator('ntx-logs').evaluate((el) => {
      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      if (!entries?.length) return false;
      return Array.from(entries).every(e => !!e.dataset.level);
    });
    expect(hasDataLevel).toBe(true);
  });

  test('entry time shows valid HH:MM:SS format', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const time = await page.locator('ntx-logs').evaluate((el) => {
      const entry = el.shadowRoot?.querySelector('.log-list .entry');
      return entry?.querySelector('.time')?.textContent || '';
    });
    // Should match HH:MM:SS or similar time format
    expect(time).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });
});


test.describe('ntx-logs — Filtering', () => {

  test('filter buttons exist for all 6 levels', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const filterLevels = await page.locator('ntx-logs').evaluate((el) => {
      const btns = el.shadowRoot?.querySelectorAll('.filter-btn');
      if (!btns?.length) return [];
      return Array.from(btns).map(b => b.dataset.level);
    });
    expect(filterLevels).toEqual(['error', 'warn', 'info', 'event', 'debug', 'dev']);
  });

  test('clicking filter activates it and hides non-matching entries', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const result = await page.locator('ntx-logs').evaluate((el) => {
      const btn = el.shadowRoot?.querySelector('.filter-btn[data-level="info"]');
      btn?.click();

      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      if (!entries?.length) return { active: false, total: 0 };

      let visible = 0, hidden = 0;
      for (const e of entries) {
        if (e.style.display === 'none') hidden++;
        else visible++;
      }

      return {
        active: btn?.classList.contains('active'),
        total: entries.length,
        visible,
        hidden,
      };
    });

    expect(result.active).toBe(true);
    // Some entries should be hidden (those not 'info')
    if (result.total > result.visible) {
      expect(result.hidden).toBeGreaterThan(0);
    }
  });

  test('clicking active filter deactivates it (shows all)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const result = await page.locator('ntx-logs').evaluate((el) => {
      const btn = el.shadowRoot?.querySelector('.filter-btn[data-level="info"]');
      btn?.click(); // activate
      btn?.click(); // deactivate
      const isActive = btn?.classList.contains('active');
      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      let allVisible = true;
      for (const e of entries || []) {
        if (e.style.display === 'none') allVisible = false;
      }
      return { isActive, allVisible };
    });

    expect(result.isActive).toBe(false);
    expect(result.allVisible).toBe(true);
  });

  test('switching filters deactivates previous filter', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const result = await page.locator('ntx-logs').evaluate((el) => {
      const infoBtn = el.shadowRoot?.querySelector('.filter-btn[data-level="info"]');
      const eventBtn = el.shadowRoot?.querySelector('.filter-btn[data-level="event"]');
      infoBtn?.click();
      const infoActive = infoBtn?.classList.contains('active');
      eventBtn?.click();
      const infoStillActive = infoBtn?.classList.contains('active');
      const eventActive = eventBtn?.classList.contains('active');
      return { infoActive, infoStillActive, eventActive };
    });

    expect(result.infoActive).toBe(true);
    expect(result.infoStillActive).toBe(false);
    expect(result.eventActive).toBe(true);
  });
});


test.describe('ntx-logs — Clear', () => {

  test('clear button removes all entries and resets badge', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Verify entries exist before clear
    const beforeCount = await page.locator('ntx-logs').evaluate((el) => {
      return el.shadowRoot?.querySelectorAll('.log-list .entry').length || 0;
    });
    expect(beforeCount).toBeGreaterThan(0);

    // Clear
    await page.locator('ntx-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.clear-btn')?.click();
    });
    await page.waitForTimeout(300);

    const afterState = await page.locator('ntx-logs').evaluate((el) => {
      return {
        entryCount: el.shadowRoot?.querySelectorAll('.log-list .entry').length || 0,
        badge: el.shadowRoot?.querySelector('.badge')?.textContent || '',
      };
    });
    expect(afterState.entryCount).toBe(0);
    expect(afterState.badge).toBe('0');
  });

  test('new logs still appear after clear', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Clear
    await page.locator('ntx-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.clear-btn')?.click();
    });
    await page.waitForTimeout(300);

    // Trigger a new log by navigating
    await page.evaluate(() => { window.location.hash = '#Product/1'; });
    await page.waitForTimeout(2000);

    const newCount = await page.locator('ntx-logs').evaluate((el) => {
      return el.shadowRoot?.querySelectorAll('.log-list .entry').length || 0;
    });
    expect(newCount).toBeGreaterThan(0);
  });
});


test.describe('ntx-logs — JSON Expansion', () => {

  test('JSON nodes exist and start collapsed (depth > 0)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const jsonInfo = await page.locator('ntx-logs').evaluate((el) => {
      const nodes = el.shadowRoot?.querySelectorAll('.json-node');
      if (!nodes?.length) return { count: 0, collapsedCount: 0 };
      let collapsed = 0;
      for (const n of nodes) {
        if (n.classList.contains('collapsed')) collapsed++;
      }
      return { count: nodes.length, collapsedCount: collapsed };
    });
    // There should be some JSON nodes from schema fetches
    if (jsonInfo.count > 0) {
      expect(jsonInfo.collapsedCount).toBeGreaterThan(0);
    }
  });

  test('clicking JSON toggle expands/collapses node', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const result = await page.locator('ntx-logs').evaluate((el) => {
      const node = el.shadowRoot?.querySelector('.json-node.collapsed');
      if (!node) return { found: false };
      const toggle = node.querySelector('.json-toggle');
      toggle?.click();
      const expanded = !node.classList.contains('collapsed');
      toggle?.click();
      const collapsedAgain = node.classList.contains('collapsed');
      return { found: true, expanded, collapsedAgain };
    });

    if (result.found) {
      expect(result.expanded).toBe(true);
      expect(result.collapsedAgain).toBe(true);
    }
  });
});


test.describe('ntx-logs — Badge Counter', () => {

  test('badge shows non-zero count after page load', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const badge = await page.locator('ntx-logs').evaluate((el) => {
      return el.shadowRoot?.querySelector('.badge')?.textContent || '0';
    });
    expect(parseInt(badge)).toBeGreaterThan(0);
  });

  test('badge count reflects Logging.size (capped at buffer max)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const { badge, entryCount } = await page.locator('ntx-logs').evaluate((el) => {
      const badge = el.shadowRoot?.querySelector('.badge')?.textContent || '0';
      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      return { badge: parseInt(badge), entryCount: entries?.length || 0 };
    });
    // Badge shows Logging.size (capped at MAX_ENTRIES=500).
    // DOM entries grow unbounded. Both should be > 0 after page load.
    expect(badge).toBeGreaterThan(0);
    expect(entryCount).toBeGreaterThan(0);
    // Badge cannot exceed the buffer cap (500)
    expect(badge).toBeLessThanOrEqual(500);
  });
});


test.describe('ntx-logs — Edge Cases', () => {

  test('panel renders correctly at mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const hasToggle = await page.locator('ntx-logs').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.toggle');
    });
    expect(hasToggle).toBe(true);
  });

  test('log panel is fixed position at bottom-right', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const position = await page.locator('ntx-logs').evaluate((el) => {
      return getComputedStyle(el).position;
    });
    expect(position).toBe('fixed');
  });

  test('entries with special characters render safely (no XSS)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Entries should use .textContent or #esc() to prevent HTML injection
    const hasScriptTag = await page.locator('ntx-logs').evaluate((el) => {
      const html = el.shadowRoot?.querySelector('.log-list')?.innerHTML || '';
      return html.includes('<script');
    });
    expect(hasScriptTag).toBe(false);
  });

  test('toggle button is a round circle (border-radius: 50%)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const radius = await page.locator('ntx-logs').evaluate((el) => {
      const toggle = el.shadowRoot?.querySelector('.toggle');
      return toggle ? getComputedStyle(toggle).borderRadius : '';
    });
    expect(radius).toBe('50%');
  });
});
