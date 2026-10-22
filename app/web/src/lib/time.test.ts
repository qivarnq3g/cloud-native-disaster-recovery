import { expect, it } from 'vitest';

import { formatTime } from './time';

it('hiện giờ Việt Nam', () => {
  expect(formatTime('2026-10-09T07:05:00Z')).toBe('14:05, 09/10/2026');
});
