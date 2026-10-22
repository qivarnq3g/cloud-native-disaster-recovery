import { crc32, deflateSync } from 'node:zlib';

import type { APIRequestContext } from '@playwright/test';

export const API = process.env.PUBLIC_API_URL ?? 'http://127.0.0.1:8080';
export const CODE = process.env.TEST_SECRET_CODE ?? 'test-code-0123456789';

function chunk(kind: string, data: Buffer): Buffer {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const name = Buffer.from(kind, 'ascii');
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([name, data])) >>> 0);
  return Buffer.concat([length, name, data, crc]);
}

export function createPng(width: number, height: number): Buffer {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  const raw = Buffer.alloc(height * (1 + width * 3));
  for (let y = 0; y < height; y++) {
    const offset = y * (1 + width * 3);
    for (let x = 0; x < width; x++) {
      const i = offset + 1 + x * 3;
      raw[i] = x % 256;
      raw[i + 1] = y % 256;
      raw[i + 2] = (x + y) % 256;
    }
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

export async function postViaApi(request: APIRequestContext, title: string, width: number, height: number): Promise<{ id: string; title: string }> {
  const r = await request.post(`${API}/v1/posts`, {
    headers: { Authorization: `Bearer ${CODE}` },
    multipart: {
      idempotency_key: crypto.randomUUID(),
      title: title,
      description: 'Bài thử tự động',
      image: { name: 'image.png', mimeType: 'image/png', buffer: createPng(width, height) },
    },
  });
  if (r.status() !== 201) throw new Error(`đăng thử lỗi ${r.status()}: ${await r.text()}`);
  return r.json();
}
