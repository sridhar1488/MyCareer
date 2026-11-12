import { test, expect } from '@playwright/test';

const password = process.env.MI_E2E_PASSWORD!;
for (const role of ['employee', 'manager', 'hr', 'admin']) {
  test(`${role} signs in, reloads session, changes view and signs out`, async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('Work email').fill(`${role}.e2e@example.org`);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    const home = role === 'employee' ? 'My appraisal' : 'Dashboard';
    await expect(page.getByRole('heading', { name: home, exact: true })).toBeVisible();
    const welcome = page.locator('.welcome-panel');
    await expect(welcome.getByRole('heading', { name: 'Welcome, Test.', exact: true })).toBeVisible();
    await expect(page.getByText(`Test ${role[0].toUpperCase() + role.slice(1)}`, { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: home, exact: true })).toBeVisible();
    if (role === 'employee') {
      await expect(welcome.getByText('View your assigned appraisal cycles and continue your self-assessment.')).toBeVisible();
    }
    if (role === 'manager') {
      await page.getByRole('button', { name: 'My appraisal', exact: true }).click();
      await page.reload();
      await expect(page.getByRole('heading', { name: 'My appraisal', exact: true })).toBeVisible();
      await expect(page.locator('.welcome-panel')).toHaveCount(0);
    }
    if (role === 'admin') {
      const viewport = page.viewportSize()!;
      await page.setViewportSize({ width: 1000, height: 540 });
      await expect(page.locator('.sidebar').getByRole('img', { name: 'MedImpact International' })).toBeVisible();
      await expect(page.locator('.sidebar').getByText('Your Workspace', { exact: true })).toBeVisible();
      await expect(page.locator('.sidebar').getByText('Room to grow.', { exact: true })).toBeInViewport({ ratio: 1 });
      await expect(page.getByRole('navigation', { name: 'Main navigation' })
        .getByRole('button', { name: 'User directory', exact: true })).toBeVisible();
      const fits = await page.locator('.sidebar').evaluate(element => {
        const nav = element.querySelector('nav')!;
        const logo = element.querySelector('.sidebar-brand')!.getBoundingClientRect();
        const label = element.querySelector('.sidebar-label')!.getBoundingClientRect();
        const tagline = element.querySelector('.sidebar-tagline')!.getBoundingClientRect();
        return label.top - logo.bottom >= 8 && nav.getBoundingClientRect().bottom < tagline.top &&
          tagline.bottom <= innerHeight && element.scrollHeight <= element.clientHeight;
      });
      expect(fits).toBe(true);
      const sidebar = (await page.locator('.sidebar').boundingBox())!;
      const header = (await page.locator('.topbar').boundingBox())!;
      expect(header.x).toBeCloseTo(sidebar.x + sidebar.width);
      expect(header.y).toBeCloseTo(sidebar.y);
      await page.setViewportSize({ width: 390, height: 844 });
      const mobileSidebar = (await page.locator('.sidebar').boundingBox())!;
      const mobileHeader = (await page.locator('.topbar').boundingBox())!;
      expect(mobileSidebar.y).toBeCloseTo(mobileHeader.y + mobileHeader.height);
      await page.setViewportSize(viewport);
    }
    const profileMenu = page.getByLabel('User profile', { exact: true });
    await profileMenu.click();
    await expect(page.getByRole('navigation', { name: 'Profile navigation' })
      .getByRole('button', { name: 'User directory', exact: true })).toHaveCount(0);
    const admin = page.getByRole('button', { name: 'Account overview' });
    if (role === 'admin' || role === 'hr') {
      await admin.click();
      await expect(page.getByText('Total accounts', { exact: true })).toBeVisible();
      await profileMenu.click();
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
  await page.getByLabel('New password', { exact: true }).fill(`${password}-change`);
  await page.getByLabel('Confirm new password').fill(`${password}-change`);
  await page.getByRole('button', { name: 'Save new password' }).click();
  const passwordChanged = page.getByText('Password changed. Other sessions have been signed out.', { exact: true });
  await expect(page.getByRole('status').and(passwordChanged)).toBeVisible();
  await page.getByLabel('User profile', { exact: true }).click();
  await page.getByRole('button', { name: 'Your profile', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
});

test('personal profile photo persists across reloads and can be removed', async ({ page }) => {
  const response = await page.request.post('/api/v1/auth/login', {
    headers: { Origin: 'http://127.0.0.1:5173' },
    data: { email: 'employee.e2e@example.org', password },
  });
  expect(response.ok()).toBe(true);
  await page.goto('/');
  await page.getByLabel('User profile', { exact: true }).click();
  await page.getByRole('button', { name: 'Your profile', exact: true }).click();
  const photo = page.getByLabel('Add profile picture', { exact: true });
  await photo.setInputFiles({ name: 'fake.png', mimeType: 'image/png', buffer: Buffer.from('invalid image') });
  await expect(page.getByRole('alert')).toContainText('Choose a valid JPEG, PNG, or WebP image.');
  await photo.setInputFiles({
    name: 'portrait.png', mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAE0lEQVR4nGNsYGhggAEmOAsvBwAzBAEI14KrBQAAAABJRU5ErkJggg==', 'base64'),
  });
  await expect(page.getByRole('status').filter({ hasText: 'Profile picture updated.' })).toBeVisible();
  await page.reload();
  const avatar = page.locator('.topbar .profile-avatar img');
  await expect(avatar).toBeVisible();
  await expect.poll(() => avatar.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBe(192);
  await page.getByLabel('User profile', { exact: true }).click();
  await page.getByRole('button', { name: 'Your profile', exact: true }).click();
  await page.getByRole('button', { name: 'Remove profile picture', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Profile picture removed.' })).toBeVisible();
  await expect(avatar).toHaveCount(0);
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

test('sign-in keeps its original content in view on desktop and mobile', async ({ page }) => {
  await page.goto('/');
  const accessNote = page.getByText('Use your registered organization account.', { exact: false });
  const formFooter = page.getByText('Make progress, together.', { exact: true });
  async function expectLoginFits() {
    await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeInViewport({ ratio: 1 });
    await expect(accessNote).toBeInViewport({ ratio: 1 });
    await expect(formFooter).toBeInViewport({ ratio: 1 });
    const fits = await page.evaluate(() => {
      const viewport = document.documentElement;
      return viewport.scrollWidth <= innerWidth && viewport.scrollHeight <= innerHeight;
    });
    expect(fits).toBe(true);
  }
  for (const [width, height] of [[1280, 720], [1024, 576], [390, 640], [320, 568]]) {
    await page.setViewportSize({ width, height });
    await expectLoginFits();
    if (width > 720) {
      await expect(page.getByText('Your performance. Your development. Our shared progress.')).toBeInViewport({ ratio: 1 });
      await expect(page.getByText('MedImpact International · People & performance')).toBeInViewport({ ratio: 1 });
    }
  }
  await page.getByLabel('Work email').fill('missing@example.org');
  await page.getByLabel('Password', { exact: true }).fill('invalid password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('Email or password is incorrect.');
  await expectLoginFits();
  await page.getByRole('button', { name: 'Forgot your password?' }).click();
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('alert')).toHaveText('User is not registered. Please contact your administrator.');
});
