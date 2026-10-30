import { test, expect } from '@playwright/test';

const password = process.env.MI_E2E_PASSWORD!;
for (const role of ['employee', 'manager', 'hr', 'admin']) {
  test(`${role} signs in, reloads session, changes view and signs out`, async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('Work email').fill(`${role}.e2e@example.org`);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'My appraisal', exact: true })).toBeVisible();
    await expect(page.getByText(`Test ${role[0].toUpperCase() + role.slice(1)}`, { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: 'My appraisal', exact: true })).toBeVisible();
    const admin = page.getByRole('button', { name: 'Account overview' });
    if (role === 'admin' || role === 'hr') {
      await admin.click();
      await expect(page.getByText('Total accounts', { exact: true })).toBeVisible();
    } else {
      await expect(admin).toHaveCount(0);
      const denied = await page.request.get('/api/v1/admin/summary');
      expect(denied.status()).toBe(403);
    }
    await page.getByRole('button', { name: 'Account security', exact: true }).click();
    await expect(page.getByLabel('Current password')).toBeVisible();
    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  });
}

test('temporary credential must be replaced before continuing', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Work email').fill('temporary.e2e@example.org');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Choose your own password' })).toBeVisible();
  await page.getByLabel('Current password').fill(password);
  await page.getByLabel('New password', { exact: true }).fill(`${password}-changed`);
  await page.getByLabel('Confirm new password').fill(`${password}-changed`);
  await page.getByRole('button', { name: 'Save new password' }).click();
  await expect(page.getByRole('status')).toHaveText('Password changed. Other sessions have been signed out.');
  await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
});

test('reset link is consumed once and removed from the address bar', async ({ page }) => {
  await page.goto(`/#reset=${process.env.MI_E2E_RESET_TOKEN}`);
  await expect(page.getByRole('heading', { name: 'Set a new password' })).toBeVisible();
  await expect(page).toHaveURL('http://127.0.0.1:5173/');
  await page.getByLabel('New password', { exact: true }).fill(`${password}-reset`);
  await page.getByLabel('Confirm new password').fill(`${password}-reset`);
  await page.getByRole('button', { name: 'Save new password' }).click();
  await expect(page.getByText('Password reset complete. Sign in with your new password.')).toBeVisible();
  await page.goto(`/#reset=${process.env.MI_E2E_RESET_TOKEN}`);
  await page.getByLabel('New password', { exact: true }).fill(`${password}-again`);
  await page.getByLabel('Confirm new password').fill(`${password}-again`);
  await page.getByRole('button', { name: 'Save new password' }).click();
  await expect(page.getByRole('alert')).toHaveText('This reset link is invalid or expired.');
});

test('mobile login has no horizontal overflow and displays an authentication error', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByLabel('Work email').fill('missing@example.org');
  await page.getByLabel('Password', { exact: true }).fill('invalid password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('Email or password is incorrect.');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Forgot your password?' }).click();
  await page.getByRole('button', { name: 'Request reset assistance' }).click();
  await expect(page.getByRole('status')).toContainText('Contact your account administrator');
});
