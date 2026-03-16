import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { showToast, clearToasts } from '../../utils/Toast.js';

describe('Toast.js', () => {

  beforeEach(() => {
    clearToasts();
    // Remove any leftover container from previous tests
    const existing = document.getElementById('ntx-toast-container');
    if (existing) existing.remove();
  });

  afterEach(() => {
    clearToasts();
    const existing = document.getElementById('ntx-toast-container');
    if (existing) existing.remove();
  });

  describe('showToast(message, type, duration)', () => {

    it('should create a toast element in the DOM', () => {
      showToast('Test error');
      const container = document.getElementById('ntx-toast-container');
      expect(container).not.toBeNull();
      expect(container.children.length).toBe(1);
    });

    it('should set the correct text content', () => {
      const toast = showToast('Something went wrong');
      expect(toast.textContent).toBe('Something went wrong');
    });

    it('should apply error class by default', () => {
      const toast = showToast('Error');
      expect(toast.classList.contains('ntx-toast--error')).toBe(true);
    });

    it('should apply success class when type is success', () => {
      const toast = showToast('Saved', 'success');
      expect(toast.classList.contains('ntx-toast--success')).toBe(true);
    });

    it('should apply info class when type is info', () => {
      const toast = showToast('Loading', 'info');
      expect(toast.classList.contains('ntx-toast--info')).toBe(true);
    });

    it('should stack multiple toasts', () => {
      showToast('First error');
      showToast('Second error');
      showToast('Third error');
      const container = document.getElementById('ntx-toast-container');
      expect(container.children.length).toBe(3);
    });

    it('should return null for empty message', () => {
      const result = showToast('');
      expect(result).toBeNull();
    });

    it('should return null for null message', () => {
      const result = showToast(null);
      expect(result).toBeNull();
    });

    it('should return null for undefined message', () => {
      const result = showToast(undefined);
      expect(result).toBeNull();
    });

    it('should auto-dismiss after the specified duration', async () => {
      vi.useFakeTimers();
      showToast('Will vanish', 'error', 100);
      const container = document.getElementById('ntx-toast-container');
      expect(container.children.length).toBe(1);

      // Advance past the dismiss timeout
      vi.advanceTimersByTime(100);
      // Advance past the fade-out transition
      vi.advanceTimersByTime(400);

      expect(container.children.length).toBe(0);
      vi.useRealTimers();
    });

    it('should dismiss on click', async () => {
      vi.useFakeTimers();
      const toast = showToast('Click me', 'error', 60000);
      const container = document.getElementById('ntx-toast-container');
      expect(container.children.length).toBe(1);

      toast.click();
      // Advance past the fade-out transition
      vi.advanceTimersByTime(400);

      expect(container.children.length).toBe(0);
      vi.useRealTimers();
    });

    it('should add the ntx-toast--visible class after creation via rAF', async () => {
      // jsdom's requestAnimationFrame runs asynchronously as a microtask.
      // We wait for it to fire by yielding to the event loop.
      const toast = showToast('Visible test');
      // Wait for rAF callback to execute
      await new Promise(resolve => setTimeout(resolve, 50));
      expect(toast.classList.contains('ntx-toast--visible')).toBe(true);
    });
  });

  describe('clearToasts()', () => {

    it('should remove all toasts', () => {
      showToast('One');
      showToast('Two');
      showToast('Three');
      const container = document.getElementById('ntx-toast-container');
      expect(container.children.length).toBe(3);

      clearToasts();
      expect(container.children.length).toBe(0);
    });

    it('should be safe to call when no toasts exist', () => {
      expect(() => clearToasts()).not.toThrow();
    });
  });

  describe('style injection', () => {

    it('should inject a <style> element into <head>', () => {
      showToast('Style test');
      const styles = document.querySelectorAll('style');
      const hasToastStyle = Array.from(styles).some(s =>
        s.textContent.includes('.ntx-toast')
      );
      expect(hasToastStyle).toBe(true);
    });

    it('should only inject styles once', () => {
      showToast('First');
      showToast('Second');
      const styles = document.querySelectorAll('style');
      const toastStyles = Array.from(styles).filter(s =>
        s.textContent.includes('.ntx-toast')
      );
      expect(toastStyles.length).toBe(1);
    });
  });

  describe('container', () => {

    it('should be positioned fixed at the bottom-right', () => {
      showToast('Position test');
      const container = document.getElementById('ntx-toast-container');
      expect(container.style.position).toBe('fixed');
      expect(container.style.bottom).toBe('1.5rem');
      expect(container.style.right).toBe('1.5rem');
    });

    it('should have a high z-index', () => {
      showToast('Z-index test');
      const container = document.getElementById('ntx-toast-container');
      expect(parseInt(container.style.zIndex)).toBeGreaterThanOrEqual(10000);
    });

    it('should reuse existing container', () => {
      showToast('One');
      showToast('Two');
      const containers = document.querySelectorAll('#ntx-toast-container');
      expect(containers.length).toBe(1);
    });
  });
});
