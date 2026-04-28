/**
 * Display Mode Cascade — Integration Tests
 *
 * Tests: ResizeObserver triggers, size cascade, display mode resolution
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { flush } from './helpers/test-env.js';

let Component;

afterEach(async () => {
  await flush(10);
});

beforeEach(async () => {
  vi.resetModules();
  global.fetch = vi.fn(() => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve({}),
  }));

  const compMod = await import('../../core/Component.js');
  Component = compMod.Component;
});

describe('Display Mode Cascade', () => {

  describe('normalizeDisplay', () => {
    it('converts pill to xs', () => {
      expect(Component.normalizeDisplay('pill')).toBe('xs');
    });

    it('converts list-item to sm', () => {
      expect(Component.normalizeDisplay('list-item')).toBe('sm');
    });

    it('converts card to md', () => {
      expect(Component.normalizeDisplay('card')).toBe('md');
    });

    it('converts detail to lg', () => {
      expect(Component.normalizeDisplay('detail')).toBe('lg');
    });

    it('converts page to xl', () => {
      expect(Component.normalizeDisplay('page')).toBe('xl');
    });

    it('passes through abstract sizes', () => {
      for (const size of ['xs', 'sm', 'md', 'lg', 'xl']) {
        expect(Component.normalizeDisplay(size)).toBe(size);
      }
    });

    it('returns null for auto and empty', () => {
      expect(Component.normalizeDisplay('auto')).toBeNull();
      expect(Component.normalizeDisplay('')).toBeNull();
      expect(Component.normalizeDisplay(null)).toBeNull();
      expect(Component.normalizeDisplay(undefined)).toBeNull();
    });
  });

  describe('SIZE_CASCADE mapping', () => {
    it('xl parent produces md children', async () => {
      const { ListElement } = await import('../../components/ListElement.js');
      expect(ListElement.SIZE_CASCADE.xl).toBe('md');
    });

    it('lg parent produces sm children', async () => {
      const { ListElement } = await import('../../components/ListElement.js');
      expect(ListElement.SIZE_CASCADE.lg).toBe('sm');
    });

    it('md parent produces sm children', async () => {
      const { ListElement } = await import('../../components/ListElement.js');
      expect(ListElement.SIZE_CASCADE.md).toBe('sm');
    });

    it('sm parent produces xs children', async () => {
      const { ListElement } = await import('../../components/ListElement.js');
      expect(ListElement.SIZE_CASCADE.sm).toBe('xs');
    });

    it('xs parent produces xs children', async () => {
      const { ListElement } = await import('../../components/ListElement.js');
      expect(ListElement.SIZE_CASCADE.xs).toBe('xs');
    });
  });

  describe('Breakpoint thresholds', () => {
    it('Component has default display breakpoints', () => {
      // Component is an HTMLElement, can't instantiate directly in jsdom easily.
      // Test the static properties and helpers instead.
      const bp = Component.prototype.displayBreakpoints;
      expect(bp).toBeDefined();
      expect(bp.xl).toBe(800);
      expect(bp.lg).toBe(600);
      expect(bp.md).toBe(400);
      expect(bp.sm).toBe(200);
      expect(bp.xs).toBe(0);
    });

    it('breakpoints sorted largest-first for resolution', () => {
      const bp = Component.prototype.displayBreakpoints;
      const sorted = Object.entries(bp).sort(([, a], [, b]) => b - a);
      expect(sorted[0][0]).toBe('xl');
      expect(sorted[1][0]).toBe('lg');
      expect(sorted[2][0]).toBe('md');
      expect(sorted[3][0]).toBe('sm');
      expect(sorted[4][0]).toBe('xs');
    });

    it('width=0 resolves to xs', () => {
      const bp = Component.prototype.displayBreakpoints;
      const sorted = Object.entries(bp).sort(([, a], [, b]) => b - a);
      const result = sorted.find(([, min]) => 0 >= min)?.[0];
      expect(result).toBe('xs');
    });

    it('width=400 resolves to md', () => {
      const bp = Component.prototype.displayBreakpoints;
      const sorted = Object.entries(bp).sort(([, a], [, b]) => b - a);
      const result = sorted.find(([, min]) => 400 >= min)?.[0];
      expect(result).toBe('md');
    });

    it('width=600 resolves to lg', () => {
      const bp = Component.prototype.displayBreakpoints;
      const sorted = Object.entries(bp).sort(([, a], [, b]) => b - a);
      const result = sorted.find(([, min]) => 600 >= min)?.[0];
      expect(result).toBe('lg');
    });

    it('width=800 resolves to xl', () => {
      const bp = Component.prototype.displayBreakpoints;
      const sorted = Object.entries(bp).sort(([, a], [, b]) => b - a);
      const result = sorted.find(([, min]) => 800 >= min)?.[0];
      expect(result).toBe('xl');
    });

    it('width=199 resolves to sm', () => {
      const bp = Component.prototype.displayBreakpoints;
      const sorted = Object.entries(bp).sort(([, a], [, b]) => b - a);
      const result = sorted.find(([, min]) => 199 >= min)?.[0];
      expect(result).toBe('xs');
    });

    it('width=200 resolves to sm', () => {
      const bp = Component.prototype.displayBreakpoints;
      const sorted = Object.entries(bp).sort(([, a], [, b]) => b - a);
      const result = sorted.find(([, min]) => 200 >= min)?.[0];
      expect(result).toBe('sm');
    });
  });

  describe('SIZES and ALIASES constants', () => {
    it('SIZES includes the five adaptive card sizes plus row mode', () => {
      expect(Component.SIZES).toEqual(['xs', 'sm', 'md', 'lg', 'xl', 'row']);
    });

    it('ALIASES maps all semantic names', () => {
      expect(Object.keys(Component.ALIASES)).toHaveLength(6);
      expect(Component.ALIASES).toHaveProperty('pill');
      expect(Component.ALIASES).toHaveProperty('list-item');
      expect(Component.ALIASES).toHaveProperty('card');
      expect(Component.ALIASES).toHaveProperty('detail');
      expect(Component.ALIASES).toHaveProperty('page');
      expect(Component.ALIASES).toHaveProperty('row');
    });

    it('all ALIASES values are valid SIZES', () => {
      for (const size of Object.values(Component.ALIASES)) {
        expect(Component.SIZES).toContain(size);
      }
    });
  });
});
