import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getCurrentTime } from '../../utils/DateFormat.js';

describe('DateFormat.js', () => {

  describe('Date.prototype.toStringDM', () => {
    it('should be defined on Date prototype', () => {
      expect(typeof Date.prototype.toStringDM).toBe('function');
    });

    it('should format a date as DD-MM', () => {
      const d = new Date(2024, 5, 15); // June 15, 2024
      const result = Date.prototype.toStringDM(d);
      expect(result).toBe('15-5');
    });

    it('should handle single-digit day and month', () => {
      const d = new Date(2024, 0, 3); // Jan 3
      const result = Date.prototype.toStringDM(d);
      expect(result).toBe('3-0'); // getMonth() is 0-indexed
    });
  });

  describe('Date.prototype.toStringDMY', () => {
    it('should be defined on Date prototype', () => {
      expect(typeof Date.prototype.toStringDMY).toBe('function');
    });

    it('should format a date as DD-MM-YYYY', () => {
      const d = new Date(2024, 11, 25); // Dec 25, 2024
      const result = Date.prototype.toStringDMY(d);
      expect(result).toBe('25-11-2024');
    });

    it('should handle different years', () => {
      const d = new Date(2000, 0, 1); // Jan 1, 2000
      const result = Date.prototype.toStringDMY(d);
      expect(result).toBe('1-0-2000');
    });
  });

  describe('getCurrentTime()', () => {
    it('should return a string in HH:MM format', () => {
      const result = getCurrentTime();
      expect(result).toMatch(/^\d{2}:\d{2}$/);
    });

    it('should pad single-digit minutes with zero', () => {
      const realDate = Date;
      const mockDate = new Date(2024, 0, 1, 14, 5); // 14:05
      vi.useFakeTimers();
      vi.setSystemTime(mockDate);
      const result = getCurrentTime();
      expect(result).toBe('14:05');
      vi.useRealTimers();
    });

    it('should pad single-digit hours with zero', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2024, 0, 1, 9, 30)); // 09:30
      const result = getCurrentTime();
      expect(result).toBe('09:30');
      vi.useRealTimers();
    });

    it('should handle midnight (00:00)', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2024, 0, 1, 0, 0));
      const result = getCurrentTime();
      expect(result).toBe('00:00');
      vi.useRealTimers();
    });

    it('should handle 23:59', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2024, 0, 1, 23, 59));
      const result = getCurrentTime();
      expect(result).toBe('23:59');
      vi.useRealTimers();
    });
  });

  describe('Date.prototype.timeNow', () => {
    it('should be defined on Date prototype', () => {
      expect(typeof Date.prototype.timeNow).toBe('function');
    });
  });
});
