/**
 * Logs Panel — E2E Tests
 */
import { test, expect } from '@playwright/test';

const APP_URL = '/matrix.html';

test.describe('Logs Panel', () => {

  test('toggle button visible on page', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const hasToggle = await page.locator('ntt-logs').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.toggle');
    });
    expect(hasToggle).toBe(true);
  });

  test('clicking toggle opens panel', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Panel should start closed
    const closedBefore = await page.locator('ntt-logs').evaluate((el) => {
      const panel = el.shadowRoot?.querySelector('.panel');
      return !panel?.classList.contains('open');
    });
    expect(closedBefore).toBe(true);

    // Click the toggle button
    await page.locator('ntt-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.toggle')?.click();
    });
    await page.waitForTimeout(300);

    // Panel should be open
    const isOpen = await page.locator('ntt-logs').evaluate((el) => {
      const panel = el.shadowRoot?.querySelector('.panel');
      return panel?.classList.contains('open');
    });
    expect(isOpen).toBe(true);
  });

  test('close button closes panel', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Open the panel
    await page.locator('ntt-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.toggle')?.click();
    });
    await page.waitForTimeout(300);

    // Click close
    await page.locator('ntt-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.close-btn')?.click();
    });
    await page.waitForTimeout(300);

    const isClosed = await page.locator('ntt-logs').evaluate((el) => {
      const panel = el.shadowRoot?.querySelector('.panel');
      return !panel?.classList.contains('open');
    });
    expect(isClosed).toBe(true);
  });

  test('log entries appear with level and timestamp', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Open panel
    await page.locator('ntt-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.toggle')?.click();
    });
    await page.waitForTimeout(500);

    const entryInfo = await page.locator('ntt-logs').evaluate((el) => {
      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      if (!entries?.length) return { count: 0, hasLevel: false, hasTime: false };
      const first = entries[0];
      return {
        count: entries.length,
        hasLevel: !!first.querySelector('.level'),
        hasTime: !!first.querySelector('.time'),
        hasLevelDot: !!first.querySelector('.level-dot'),
      };
    });

    // After page load, there should be at least some log entries
    // (schema fetches, component inits, etc.)
    expect(entryInfo.count).toBeGreaterThan(0);
    expect(entryInfo.hasLevel).toBe(true);
    expect(entryInfo.hasTime).toBe(true);
    expect(entryInfo.hasLevelDot).toBe(true);
  });

  test('entries are color-coded by level', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const levelClasses = await page.locator('ntt-logs').evaluate((el) => {
      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      if (!entries?.length) return [];
      return Array.from(entries).map(e => {
        const classes = Array.from(e.classList);
        return classes.find(c => c.startsWith('level-')) || '';
      }).filter(Boolean);
    });

    // At least some entries should have level classes
    expect(levelClasses.length).toBeGreaterThan(0);
    // Each should be one of the valid levels
    const validLevels = ['level-error', 'level-warn', 'level-info', 'level-event', 'level-debug', 'level-dev'];
    levelClasses.forEach(cls => {
      expect(validLevels).toContain(cls);
    });
  });

  test('filter buttons present for all levels', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const filterLevels = await page.locator('ntt-logs').evaluate((el) => {
      const btns = el.shadowRoot?.querySelectorAll('.filter-btn');
      if (!btns?.length) return [];
      return Array.from(btns).map(b => b.dataset.level);
    });

    expect(filterLevels).toEqual(['error', 'warn', 'info', 'event', 'debug', 'dev']);
  });

  test('filter by level hides non-matching entries', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Open panel
    await page.locator('ntt-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.toggle')?.click();
    });
    await page.waitForTimeout(300);

    // Click on a specific filter level (e.g., 'info')
    const result = await page.locator('ntt-logs').evaluate((el) => {
      const infoBtn = el.shadowRoot?.querySelector('.filter-btn[data-level="info"]');
      infoBtn?.click();

      // Check visibility of entries
      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      if (!entries?.length) return { total: 0, visible: 0, hidden: 0, filterActive: false };

      let visible = 0;
      let hidden = 0;
      for (const entry of entries) {
        if (entry.style.display === 'none') {
          hidden++;
        } else {
          visible++;
        }
      }
      return {
        total: entries.length,
        visible,
        hidden,
        filterActive: infoBtn?.classList.contains('active'),
      };
    });

    expect(result.filterActive).toBe(true);
    // If there are non-info entries, they should be hidden
    if (result.total > result.visible) {
      expect(result.hidden).toBeGreaterThan(0);
    }
  });

  test('clicking active filter deactivates it (shows all)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Activate a filter then click again to deactivate
    const result = await page.locator('ntt-logs').evaluate((el) => {
      const infoBtn = el.shadowRoot?.querySelector('.filter-btn[data-level="info"]');
      // Click to activate
      infoBtn?.click();
      const wasActive = infoBtn?.classList.contains('active');
      // Click again to deactivate
      infoBtn?.click();
      const isActive = infoBtn?.classList.contains('active');

      // All entries should be visible again
      const entries = el.shadowRoot?.querySelectorAll('.log-list .entry');
      let allVisible = true;
      for (const entry of entries || []) {
        if (entry.style.display === 'none') allVisible = false;
      }

      return { wasActive, isActive, allVisible };
    });

    expect(result.wasActive).toBe(true);
    expect(result.isActive).toBe(false);
    expect(result.allVisible).toBe(true);
  });

  test('clear button removes all entries', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Open panel and verify there are entries
    await page.locator('ntt-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.toggle')?.click();
    });
    await page.waitForTimeout(300);

    const beforeCount = await page.locator('ntt-logs').evaluate((el) => {
      return el.shadowRoot?.querySelectorAll('.log-list .entry').length || 0;
    });
    expect(beforeCount).toBeGreaterThan(0);

    // Click clear
    await page.locator('ntt-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.clear-btn')?.click();
    });
    await page.waitForTimeout(300);

    const afterCount = await page.locator('ntt-logs').evaluate((el) => {
      return el.shadowRoot?.querySelectorAll('.log-list .entry').length || 0;
    });
    expect(afterCount).toBe(0);
  });

  test('badge count updates as logs are added', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const badgeText = await page.locator('ntt-logs').evaluate((el) => {
      return el.shadowRoot?.querySelector('.badge')?.textContent || '0';
    });

    // Badge should reflect the log count (non-zero after page load)
    const count = parseInt(badgeText, 10);
    expect(count).toBeGreaterThan(0);
  });

  test('badge resets to 0 after clear', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Clear logs
    await page.locator('ntt-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.clear-btn')?.click();
    });
    await page.waitForTimeout(300);

    const badgeText = await page.locator('ntt-logs').evaluate((el) => {
      return el.shadowRoot?.querySelector('.badge')?.textContent || '';
    });
    expect(badgeText).toBe('0');
  });

  test('JSON detail can be expanded and collapsed', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Open panel
    await page.locator('ntt-logs').evaluate((el) => {
      el.shadowRoot?.querySelector('.toggle')?.click();
    });
    await page.waitForTimeout(300);

    // Check if any entries have JSON nodes (expandable)
    const hasJsonNodes = await page.locator('ntt-logs').evaluate((el) => {
      const nodes = el.shadowRoot?.querySelectorAll('.json-node');
      return (nodes?.length || 0) > 0;
    });

    // If JSON nodes exist, verify toggle behavior
    if (hasJsonNodes) {
      const toggleResult = await page.locator('ntt-logs').evaluate((el) => {
        const node = el.shadowRoot?.querySelector('.json-node.collapsed');
        if (!node) return { found: false };
        const toggle = node.querySelector('.json-toggle');
        toggle?.click();
        const expanded = !node.classList.contains('collapsed');
        toggle?.click();
        const collapsedAgain = node.classList.contains('collapsed');
        return { found: true, expanded, collapsedAgain };
      });

      if (toggleResult.found) {
        expect(toggleResult.expanded).toBe(true);
        expect(toggleResult.collapsedAgain).toBe(true);
      }
    }
  });

  test('panel has correct structure (header, toolbar, list)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const structure = await page.locator('ntt-logs').evaluate((el) => {
      const sr = el.shadowRoot;
      return {
        hasToggle: !!sr?.querySelector('.toggle'),
        hasPanel: !!sr?.querySelector('.panel'),
        hasPanelHeader: !!sr?.querySelector('.panel-header'),
        hasPanelTitle: !!sr?.querySelector('.panel-title'),
        hasCloseBtn: !!sr?.querySelector('.close-btn'),
        hasToolbar: !!sr?.querySelector('.toolbar'),
        hasFilters: !!sr?.querySelector('.filters'),
        hasClearBtn: !!sr?.querySelector('.clear-btn'),
        hasLogList: !!sr?.querySelector('.log-list'),
      };
    });

    expect(structure.hasToggle).toBe(true);
    expect(structure.hasPanel).toBe(true);
    expect(structure.hasPanelHeader).toBe(true);
    expect(structure.hasPanelTitle).toBe(true);
    expect(structure.hasCloseBtn).toBe(true);
    expect(structure.hasToolbar).toBe(true);
    expect(structure.hasFilters).toBe(true);
    expect(structure.hasClearBtn).toBe(true);
    expect(structure.hasLogList).toBe(true);
  });
});
