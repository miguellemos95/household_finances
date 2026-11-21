import { formatMonth, isMonth, shiftMonth, toIsoDate, toMonth } from './month';

describe('month helpers', () => {
  it('should move across year boundaries', () => {
    expect(shiftMonth('2025-12', 1)).toBe('2026-01');
    expect(shiftMonth('2026-01', -1)).toBe('2025-12');
  });

  it('should accept only YYYY-MM months', () => {
    expect(isMonth('2025-11')).toBe(true);
    expect(['', '2025-1', '2025-13', '11-2025'].some(isMonth)).toBe(false);
  });

  it('should format local dates without shifting them to UTC', () => {
    const lateEvening = new Date(2025, 10, 5, 23, 59);

    expect(toIsoDate(lateEvening)).toBe('2025-11-05');
    expect(toMonth(lateEvening)).toBe('2025-11');
    expect(formatMonth('2025-11')).toBe('November 2025');
  });
});
