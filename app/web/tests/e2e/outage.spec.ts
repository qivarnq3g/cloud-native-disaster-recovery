import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

import { postViaApi } from './common';

const APP_DIR = fileURLToPath(new URL('../../..', import.meta.url));
const api = (action: 'stop' | 'start') => execSync(`docker compose --profile api ${action} api`, { cwd: APP_DIR, stdio: 'inherit' });

test('mất máy chủ thì báo đang khôi phục, có lại thì báo đã chạy lại', async ({ page, request }) => {
  test.setTimeout(120_000);
  const a = await postViaApi(request, `Sự cố ${Date.now()}`, 64, 48);
  await page.goto('/view/');
  await expect(page.getByText(/Cụm chính · /)).toBeVisible();
  await expect(page.getByRole('img', { name: a.title })).toBeVisible();
  api('stop');
  try {
    await expect(page.getByText('Đang khôi phục…')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole('img', { name: a.title })).toBeVisible();
  } finally {
    api('start');
  }
  await expect(page.getByText(/Đã chạy lại sau/)).toBeVisible({ timeout: 40_000 });
  await expect(page.getByText(/Cụm chính · /)).toBeVisible();
});

test('mở trang khi máy chủ đang chết thì vẫn hiện khung và tự tải khi có lại', async ({ page, request }) => {
  test.setTimeout(120_000);
  const a = await postViaApi(request, `Mở lúc chết ${Date.now()}`, 64, 48);
  api('stop');
  try {
    await page.goto('/view/');
    await expect(page.getByText('Đang khôi phục…')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/Chưa tải được ảnh/)).toBeVisible();
  } finally {
    api('start');
  }
  await expect(page.getByRole('img', { name: a.title })).toBeVisible({ timeout: 40_000 });
});
