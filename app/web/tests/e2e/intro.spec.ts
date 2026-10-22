import { expect, test } from '@playwright/test';

test('nút Vào xem mở trang dùng, lần sau vào thẳng, ?intro vẫn xem được giới thiệu', async ({ page }) => {
  await page.route(/cdn\.jsdelivr\.net\/npm\/(three|cannon-es)@/, (r) => r.abort());
  await page.goto('/?intro');
  await page.evaluate(() => localStorage.clear());
  await page.goto('/');
  const button = page.locator('#enter-view');
  await expect(button).toHaveText('Vào xem');
  await expect(button).not.toHaveAttribute('aria-disabled', 'true');
  await button.evaluate((a: HTMLAnchorElement) => void setTimeout(() => a.click()));
  await expect(page).toHaveURL(/\/view\/?$/);
  await page.goto('/');
  await expect(page).toHaveURL(/\/view\/?$/);
  await page.goto('/?intro');
  await expect(page).toHaveURL(/intro/);
  await expect(page.locator('#enter-view')).toBeAttached();
});
