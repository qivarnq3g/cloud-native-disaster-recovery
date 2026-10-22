import { expect, test } from '@playwright/test';

import { CODE, createPng } from './common';

test('đăng ảnh điện thoại lớn: nhập mã, tự nén dưới 1 MB, bài hiện đầu lưới, nhớ mã, quên mã', async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto('/view/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByRole('button', { name: 'Đăng ảnh' }).click();
  const dialog = page.getByRole('dialog', { name: 'Đăng ảnh' });
  await dialog.getByLabel('Mã bí mật của nhóm').fill('wrong-code-0123456789');
  await dialog.getByRole('button', { name: 'Tiếp tục' }).click();
  await expect(dialog.getByRole('alert')).toHaveText('Mã không đúng.');
  await dialog.getByLabel('Mã bí mật của nhóm').fill(CODE);
  await dialog.getByRole('button', { name: 'Tiếp tục' }).click();

  const base64 = await page.evaluate(async () => {
    const c = new OffscreenCanvas(3000, 4000);
    const g = c.getContext('2d')!;
    const grad = g.createLinearGradient(0, 0, 3000, 4000);
    grad.addColorStop(0, '#1e3c72');
    grad.addColorStop(1, '#f4a261');
    g.fillStyle = grad;
    g.fillRect(0, 0, 3000, 4000);
    const image = g.getImageData(0, 0, 3000, 4000);
    for (let i = 0; i < image.data.length; i += 4) image.data[i] = (image.data[i] + ((i * 2654435761) >>> 27)) & 255;
    g.putImageData(image, 0, 0);
    const b = await c.convertToBlob({ type: 'image/jpeg', quality: 0.95 });
    const bytes = new Uint8Array(await b.arrayBuffer());
    let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s);
  });
  const image = Buffer.from(base64, 'base64');
  expect(image.length).toBeGreaterThan(1_048_576);
  await dialog.locator('input[type=file]').setInputFiles({ name: 'mobile.jpg', mimeType: 'image/jpeg', buffer: image });
  await expect(dialog.getByRole('img', { name: 'Ảnh xem trước' })).toBeVisible();
  const title = `Ảnh điện thoại ${Date.now()}`;
  await dialog.getByLabel(/Tiêu đề/).fill(title);
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/v1/posts') && r.request().method() === 'POST'),
    dialog.getByRole('button', { name: 'Đăng', exact: true }).click(),
  ]);
  expect(response.status()).toBe(201);
  const post = await response.json();
  expect(post.image_bytes).toBeLessThanOrEqual(1_048_576);
  expect(['image/webp', 'image/jpeg']).toContain(post.image_type);
  expect(post.height).toBeGreaterThan(post.width);
  await expect(dialog).toBeHidden();
  await expect(page.locator('.grid .tile').first()).toHaveAttribute('aria-label', title);

  await page.reload();
  await page.getByRole('button', { name: 'Đăng ảnh' }).click();
  const dialog2 = page.getByRole('dialog', { name: 'Đăng ảnh' });
  await expect(dialog2.getByLabel('Mã bí mật của nhóm')).toHaveCount(0);
  await dialog2.getByRole('button', { name: 'Quên mã' }).click();
  await expect(dialog2.getByLabel('Mã bí mật của nhóm')).toBeVisible();
});

test('mã đã lưu bị đổi thì hỏi lại mã', async ({ page }) => {
  await page.goto('/view/');
  await page.evaluate(() => localStorage.setItem('secret-code', 'old-changed-code-0000'));
  await page.reload();
  await page.getByRole('button', { name: 'Đăng ảnh' }).click();
  const dialog = page.getByRole('dialog', { name: 'Đăng ảnh' });
  await dialog.locator('input[type=file]').setInputFiles({ name: 'small.png', mimeType: 'image/png', buffer: createPng(8, 8) });
  await dialog.getByLabel(/Tiêu đề/).fill('Mã cũ');
  await dialog.getByRole('button', { name: 'Đăng', exact: true }).click();
  await expect(dialog.getByRole('alert')).toHaveText('Mã đã bị đổi, nhập lại mã.');
  await expect(dialog.getByLabel('Mã bí mật của nhóm')).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('secret-code'))).toBeNull();
});
