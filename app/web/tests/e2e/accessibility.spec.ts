import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { postViaApi } from './common';

test('không có lỗi trợ năng nghiêm trọng trên trang dùng', async ({ page, request }) => {
  await postViaApi(request, `Trợ năng ${Date.now()}`, 64, 48);
  await page.goto('/view/');
  await expect(page.locator('.grid .tile').first()).toBeVisible();
  const result = await new AxeBuilder({ page }).analyze();
  const severe = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  expect(severe.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
});

test('dùng được bằng bàn phím: Tab tới ảnh, Enter mở, Esc đóng', async ({ page, request }) => {
  await postViaApi(request, `Bàn phím ${Date.now()}`, 64, 48);
  await page.goto('/view/');
  await expect(page.locator('.grid .tile').first()).toBeVisible();
  for (let i = 0; i < 10; i++) {
    await page.keyboard.press('Tab');
    if (await page.evaluate(() => document.activeElement?.classList.contains('tile'))) break;
  }
  expect(await page.evaluate(() => document.activeElement?.classList.contains('tile'))).toBe(true);
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
});
