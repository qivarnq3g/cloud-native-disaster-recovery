export interface GridItem {
  id: string;
  width: number;
  height: number;
}

export interface Tile {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export function layoutGrid(posts: GridItem[], containerWidth: number, targetHeight: number, gap: number, caption: number): { tiles: Tile[]; totalHeight: number } {
  const tiles: Tile[] = [];
  let y = 0;
  let row: GridItem[] = [];
  let ratioSum = 0;
  const flushRow = (height: number) => {
    let x = 0;
    for (const a of row) {
      const width = (a.width / a.height) * height;
      tiles.push({ id: a.id, x, y, width, height });
      x += width + gap;
    }
    y += height + caption + gap;
    row = [];
    ratioSum = 0;
  };
  for (const a of posts) {
    row.push(a);
    ratioSum += a.width / a.height;
    if (ratioSum * targetHeight + gap * (row.length - 1) >= containerWidth) {
      flushRow((containerWidth - gap * (row.length - 1)) / ratioSum);
    }
  }
  if (row.length) flushRow(Math.min(targetHeight, (containerWidth - gap * (row.length - 1)) / ratioSum));
  return { tiles, totalHeight: Math.max(0, y - gap) };
}

export function targetHeight(containerWidth: number): number {
  return containerWidth < 600 ? Math.round((containerWidth - 8) / 2 / 1.33) : 240;
}
