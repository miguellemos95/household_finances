import { parseAmount } from './amount';

describe('parseAmount', () => {
  it('should keep valid amounts as text', () => {
    expect(parseAmount('12.50')).toBe('12.50');
    expect(parseAmount(' 7 ')).toBe('7');
    expect(parseAmount('0.01')).toBe('0.01');
  });

  it.each(['', '0', '0.00', '-5', '1.234', '12,50', 'abc', '12345678901'])(
    'should reject %j',
    (value) => {
      expect(parseAmount(value)).toBeNull();
    },
  );
});
