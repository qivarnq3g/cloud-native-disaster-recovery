export const MAX_BYTES = 1_048_576;
export const MAX_EDGE = 2560;
const QUALITIES = [0.85, 0.75, 0.65, 0.55, 0.45];

export type Encoder = (width: number, height: number, quality: number) => Promise<Blob>;

export function scaledSize(width: number, height: number, edge = MAX_EDGE): [number, number] {
  const scale = Math.min(1, edge / Math.max(width, height));
  return [Math.max(1, Math.round(width * scale)), Math.max(1, Math.round(height * scale))];
}

export async function encodeWithinLimit(width: number, height: number, encode: Encoder, limit = MAX_BYTES): Promise<Blob> {
  let [r, c] = scaledSize(width, height);
  for (let attempt = 0; attempt < 6; attempt++) {
    for (const q of QUALITIES) {
      const b = await encode(r, c, q);
      if (b.size <= limit) return b;
    }
    [r, c] = [Math.max(1, Math.round(r * 0.8)), Math.max(1, Math.round(c * 0.8))];
  }
  throw new Error('Không nén được ảnh xuống dưới 1 MB.');
}

export async function compressImage(file: Blob): Promise<Blob> {
  const image = await createImageBitmap(file, { imageOrientation: 'from-image' });
  try {
    let type: 'image/webp' | 'image/jpeg' = 'image/webp';
    const encode: Encoder = async (r, c, q) => {
      const canvas = new OffscreenCanvas(r, c);
      const g = canvas.getContext('2d');
      if (!g) throw new Error('Trình duyệt không vẽ được ảnh.');
      g.drawImage(image, 0, 0, r, c);
      let b = await canvas.convertToBlob({ type: type, quality: q });
      if (b.type !== type) {
        type = 'image/jpeg';
        b = await canvas.convertToBlob({ type: type, quality: q });
      }
      return b;
    };
    return await encodeWithinLimit(image.width, image.height, encode);
  } finally {
    image.close();
  }
}
