import { expect, test } from '@playwright/test';

import { postViaApi } from './common';

test('xem lưới, mở bài, chuyển bài bằng phím, đóng bằng Esc', async ({ page, request }) => {
  const a = await postViaApi(request, `Lưới A ${Date.now()}`, 1200, 900);
  const b = await postViaApi(request, `Lưới B ${Date.now()}`, 64, 48);
  await page.goto('/view/');
  await page.getByRole('button', { name: b.title }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: b.title })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`post=${b.id}`));
  await page.keyboard.press('ArrowRight');
  await expect(dialog.getByRole('heading', { name: a.title })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(page).not.toHaveURL(/post=/);
});

test('mở thẳng đường dẫn của một bài', async ({ page, request }) => {
  const a = await postViaApi(request, `Đường dẫn ${Date.now()}`, 64, 48);
  for (let i = 0; i < 30; i++) await postViaApi(request, `Đẩy xuống ${i} ${Date.now()}`, 32, 24);
  await page.goto(`/view/?post=${a.id}`);
  await expect(page.getByRole('dialog').getByRole('heading', { name: a.title })).toBeVisible();
});
