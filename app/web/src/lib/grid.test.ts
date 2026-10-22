import { describe, expect, it } from 'vitest';

import { targetHeight, layoutGrid } from './grid';

const items = (n: number, width = 4, height = 3) => Array.from({ length: n }, (_, i) => ({ id: `a${i}`, width, height }));

describe('xếp lưới đều hàng', () => {
  it('hàng đầy vừa khít bề rộng, hàng cuối giữ chiều cao mục tiêu', () => {
    const { tiles } = layoutGrid(items(6), 1000, 240, 8, 22);
    const firstRow = tiles.filter((x) => x.y === 0);
    expect(firstRow.map((x) => x.id)).toEqual(['a0', 'a1', 'a2', 'a3']);
    const last = firstRow.at(-1)!;
    expect(last.x + last.width).toBeCloseTo(1000, 5);
    const laterRows = tiles.filter((x) => x.y > 0);
    expect(laterRows.every((x) => x.height === 240)).toBe(true);
    expect(laterRows[0].y).toBeCloseTo(firstRow[0].height + 22 + 8, 5);
  });

  it('giữ thứ tự, không chồng nhau trong một hàng', () => {
    const { tiles } = layoutGrid(items(10, 3, 4), 700, 200, 8, 22);
    expect(tiles.map((x) => x.id)).toEqual(items(10).map((x) => x.id));
    for (let i = 1; i < tiles.length; i++) {
      if (tiles[i].y === tiles[i - 1].y) expect(tiles[i].x).toBeGreaterThan(tiles[i - 1].x + tiles[i - 1].width);
    }
  });

  it('ảnh dọc rất cao ở hàng cuối không tràn bề rộng', () => {
    const { tiles } = layoutGrid([{ id: 'tall', width: 100, height: 1000 }], 50, 240, 8, 22);
    expect(tiles[0].width).toBeLessThanOrEqual(50);
  });

  it('danh sách rỗng', () => {
    expect(layoutGrid([], 1000, 240, 8, 22)).toEqual({ tiles: [], totalHeight: 0 });
  });

  it('chiều cao mục tiêu: điện thoại khoảng hai ảnh một hàng', () => {
    expect(targetHeight(390)).toBe(144);
    expect(targetHeight(1280)).toBe(240);
  });
});
