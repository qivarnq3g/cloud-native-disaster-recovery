import { describe, expect, it } from 'vitest';

import { scaledSize, encodeWithinLimit } from './compress-image';

const blob = (bytes: number) => new Blob([new Uint8Array(bytes)]);

describe('nén ảnh', () => {
  it('thu cạnh dài về 2560, giữ tỉ lệ, không phóng to ảnh nhỏ', () => {
    expect(scaledSize(4000, 3000)).toEqual([2560, 1920]);
    expect(scaledSize(3000, 4000)).toEqual([1920, 2560]);
    expect(scaledSize(100, 50)).toEqual([100, 50]);
  });

  it('dừng ở chất lượng cao nhất vừa giới hạn', async () => {
    const calls: number[] = [];
    const b = await encodeWithinLimit(2560, 1920, async (_r, _c, q) => {
      calls.push(q);
      return blob(q >= 0.7 ? 2_000_000 : 900_000);
    });
    expect(b.size).toBe(900_000);
    expect(calls).toEqual([0.85, 0.75, 0.65]);
  });

  it('chất lượng thấp nhất vẫn quá lớn thì thu nhỏ kích thước', async () => {
    const sizes: [number, number][] = [];
    const b = await encodeWithinLimit(2560, 1920, async (r, c) => {
      sizes.push([r, c]);
      return blob(r * c > 2560 * 1920 * 0.7 ? 2_000_000 : 500_000);
    });
    expect(b.size).toBe(500_000);
    expect(sizes.at(-1)).toEqual([2048, 1536]);
  });

  it('không thể nén thì báo lỗi', async () => {
    await expect(encodeWithinLimit(100, 100, async () => blob(2_000_000))).rejects.toThrow('Không nén được ảnh');
  });
});
