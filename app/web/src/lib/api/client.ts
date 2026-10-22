import createClient from 'openapi-fetch';

import type { components, paths } from './schema';

export type Post = components['schemas']['Post'];
export type PostPage = components['schemas']['PostPage'];
export type Health = components['schemas']['Health'];

export interface UploadResult {
  status: number;
  post?: Post;
  error?: { error: string; message: string };
}

export function createApiClient(base: string) {
  return createClient<paths>({ baseUrl: base });
}

export const imageUrl = (base: string, id: string): string => `${base}/v1/posts/${id}/image`;
export const thumbnailUrl = (base: string, id: string): string => `${base}/v1/posts/${id}/thumbnail`;

export async function verifyCode(base: string, code: string): Promise<number> {
  try {
    const r = await fetch(`${base}/v1/secret-code/verify`, { method: 'POST', headers: { Authorization: `Bearer ${code}` } });
    return r.status;
  } catch {
    return 0;
  }
}

export function uploadPost(
  base: string,
  code: string,
  data: { idempotencyKey: string; title: string; description: string; image: Blob },
  progress: (fraction: number) => void,
): Promise<UploadResult> {
  return new Promise((done) => {
    const form = new FormData();
    form.append('idempotency_key', data.idempotencyKey);
    form.append('title', data.title);
    form.append('description', data.description);
    form.append('image', data.image, data.image.type === 'image/jpeg' ? 'image.jpg' : 'image.webp');
    const x = new XMLHttpRequest();
    x.open('POST', `${base}/v1/posts`);
    x.setRequestHeader('Authorization', `Bearer ${code}`);
    x.timeout = 60_000;
    x.upload.onprogress = (e) => {
      if (e.lengthComputable) progress(e.loaded / e.total);
    };
    x.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(x.responseText);
      } catch {
        body = null;
      }
      if (x.status === 200 || x.status === 201) {
        done({ status: x.status, post: body as Post });
        return;
      }
      const error = (body as UploadResult['error']) ?? { error: 'unavailable', message: 'Không gửi được, thử lại sau.' };
      done({ status: x.status, error });
    };
    const onNetworkError = () => done({ status: 0, error: { error: 'network', message: 'Mất kết nối, thử lại.' } });
    x.onerror = onNetworkError;
    x.ontimeout = onNetworkError;
    x.send(form);
  });
}
