import { expect, it } from 'vitest';

import { refractionAt } from './glass';

it('giữa tấm kính không bẻ, sát mép phải bẻ vào trong', () => {
  expect(refractionAt(0, 0, 100, 25, 25, 24)).toEqual([128, 128]);
  const [r, g] = refractionAt(99, 0, 100, 25, 25, 24);
  expect(r).toBeLessThan(128);
  expect(g).toBe(128);
  const [r2] = refractionAt(-99, 0, 100, 25, 25, 24);
  expect(r2).toBeGreaterThan(128);
});
