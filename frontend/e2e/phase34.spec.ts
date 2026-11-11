import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const password = process.env.MI_E2E_PASSWORD!;
test('HR creates an employee and cycle; employee saves extra goals, reviews and submits', async ({ page }) => {
  test.setTimeout(90000);
  const suffix = Date.now().toString();
  const email = `employee.${suffix}@example.org`;
  const employeeId = `UI-${suffix}`;
  const name = `Employee ${suffix}`;
  const cycleTitle = `Review ${suffix}`;
  await page.goto('/');
  await page.getByLabel('Work email').fill('hr.e2e@example.org');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'User directory', exact: true }).click();
  const desktop = page.viewportSize()!;
  for (const width of [desktop.width, 390]) {
    await page.setViewportSize({ width, height: desktop.height });
    for (const name of ['Import users from Excel', 'Create user']) {
      const button = page.getByRole('button', { name, exact: true });
      const labelLines = await button.evaluate(element => {
        const label = document.createRange();
        label.selectNodeContents(element);
        return label.getClientRects().length;
      });
      expect(labelLines).toBe(1);
    }
  }
  await page.setViewportSize(desktop);
  await page.getByRole('button', { name: 'Create user', exact: true }).click();
  for (const [label, value] of [['Full name', name], ['Employee ID', employeeId], ['Work email', email], ['Department', 'Engineering'], ['Job title', 'Engineer']]) {
    await page.getByLabel(label, { exact: true }).fill(value);
  }
  await page.getByLabel('Find a manager').fill('E2E-manager');
  await page.getByRole('radio', { name: /Test Manager/ }).check();
  await page.getByLabel('Date joined', { exact: true }).fill('2024-01-15');
  await page.getByLabel('Temporary password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('status').filter({hasText:'Account created'})).toBeVisible();
  await page.getByLabel('Search users').fill(employeeId);
  await expect(page.getByText(name, {exact:true})).toBeVisible();
  await page.getByRole('button', { name: 'Appraisal cycles', exact: true }).click();
  await page.getByRole('button', { name: 'Create cycle', exact: true }).click();
  await page.getByLabel('Cycle title').fill(cycleTitle);
  await page.getByLabel('Appraisal period start').fill('2026-01-01');
  await page.getByLabel('Appraisal period end').fill('2026-12-31');
  const deadline = new Date(Date.now() + 7 * 86400000);
  await page.getByLabel('Employee submission deadline').fill(deadline.toISOString().slice(0,16));
  await page.getByLabel('Find employees').fill('search with no matching participant');
  await page.getByRole('button', { name: 'Select all employees', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: /Selected \d+ eligible employee/ })).toBeVisible();
  await page.getByLabel('Find employees').fill(employeeId);
  const participant = page.getByRole('checkbox', { name: new RegExp(name) });
  await expect(participant).toBeChecked();
  await page.getByRole('button', { name: 'Clear selection', exact: true }).click();
  await expect(participant).not.toBeChecked();
  await participant.check();
  await page.getByRole('button', { name: 'Save draft cycle', exact: true }).click();
  await expect(page.getByRole('status').filter({hasText:'Draft cycle saved'})).toBeVisible();
  await page.getByRole('row').filter({ hasText: cycleTitle }).getByRole('button', { name: 'Activate cycle', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm activation', exact: true }).click();
  await expect(page.getByRole('status').filter({hasText:'Cycle activated'})).toBeVisible();
  await page.getByRole('button', { name: 'HR monitoring', exact: true }).click();
  await page.locator('summary').filter({ hasText: 'Cycle reminders' }).click();
  await page.getByLabel('Appraisal cycle for reminders').selectOption({ label: cycleTitle });
  await page.getByLabel('Manager review deadline').fill(new Date(deadline.getTime() + 14 * 86400000).toISOString().slice(0,16));
  await page.getByLabel('HR calibration deadline').fill(new Date(deadline.getTime() + 29 * 86400000).toISOString().slice(0,16));
  await page.getByRole('checkbox', { name: '3 days before each deadline' }).check();
  await page.getByRole('button', { name: 'Save reminder settings' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Reminder settings saved.' })).toBeVisible();
  await page.getByRole('button', { name: 'Preview reminder' }).click();
  await expect(page.getByText(/1 intended recipients/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send reminders' })).toBeDisabled();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await page.getByLabel('Work email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByLabel('Current password').fill(password);
  await page.getByLabel('New password', { exact: true }).fill(`${password}-person`);
  await page.getByLabel('Confirm new password').fill(`${password}-person`);
  await page.getByRole('button', { name: 'Save new password', exact: true }).click();
  await page.getByLabel('User profile', { exact: true }).click();
  await page.getByRole('button', { name: 'Your profile', exact: true }).click();
  const joiningDate = await page.evaluate(() => new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium', timeZone: 'UTC',
  }).format(new Date('2024-01-15T00:00:00Z')));
  await expect(page.getByText(joiningDate, { exact: true })).toBeVisible();
  await expect(page.getByText('India', { exact: true })).toBeVisible();
  await expect(page.getByText('Current reporting manager', { exact: true })).toBeVisible();
  await expect(page.getByText('Test Manager', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'My appraisal', exact: true }).click();
  await expect(page.getByText(/Appraisal period: 2026/)).toBeVisible();
  await expect(page.getByText(/Assigned reviewer: Test Manager/)).toBeVisible();
  await page.getByRole('button', { name: 'Open self-assessment', exact: true }).click();
  const firstDevelopmentField = page.getByLabel(
    'Most important achievements and contributions to company / project success', { exact: true }
  );
  await expect(firstDevelopmentField).toHaveAccessibleDescription('1000 of 1000 characters remaining');
  async function expectDevelopmentFocusClearance() {
    await firstDevelopmentField.focus();
    await expect(firstDevelopmentField).toHaveCSS('outline-style', 'solid');
    const clearance = await firstDevelopmentField.evaluate(field => {
      const style = getComputedStyle(field);
      const outlineTop = field.getBoundingClientRect().top
        - parseFloat(style.outlineOffset) - parseFloat(style.outlineWidth);
      return outlineTop - field.previousElementSibling!.getBoundingClientRect().bottom;
    });
    expect(clearance).toBeGreaterThanOrEqual(2);
  }
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await expectDevelopmentFocusClearance();
  }
  await page.setViewportSize({ width: 1280, height: 844 });
  const evidenceInput = page.getByLabel('Add files', { exact: true });
  await expect(evidenceInput).toHaveAttribute('accept', /\.msg/);
  const messageFixture = resolve('../backend/tests/fixtures/synthetic-outlook.msg');
  await evidenceInput.setInputFiles(messageFixture);
  const evidence = page.getByRole('listitem').filter({ hasText: 'synthetic-outlook.msg' });
  await expect(evidence).toBeVisible();
  await expect(evidence.getByRole('button', { name: 'Preview', exact: true })).toHaveCount(0);
  const downloadEvent = page.waitForEvent('download');
  await evidence.getByRole('button', { name: 'Download', exact: true }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe('synthetic-outlook.msg');
  expect(await download.failure()).toBeNull();
  await evidenceInput.setInputFiles([
    { name: 'renamed.msg', mimeType: 'application/vnd.ms-outlook', buffer: await readFile(messageFixture) },
    { name: 'additional.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\nDifferent evidence') },
  ]);
  await expect(page.getByRole('alert')).toContainText('This file is already attached as “synthetic-outlook.msg”.');
  await expect(page.getByRole('listitem').filter({ hasText: 'additional.pdf' })).toBeVisible();
  await expect(page.getByRole('listitem').filter({ hasText: 'renamed.msg' })).toHaveCount(0);
  let attachmentDeletes = 0;
  page.on('request', request => {
    if (request.method() === 'DELETE' && request.url().includes('/attachments/')) attachmentDeletes++;
  });
  page.once('dialog', async dialog => {
    expect(dialog.message()).toContain('synthetic-outlook.msg');
    await dialog.dismiss();
  });
  const remove = evidence.getByRole('button', { name: 'Remove', exact: true });
  await remove.click();
  await expect(evidence).toBeVisible();
  expect(attachmentDeletes).toBe(0);
  page.once('dialog', dialog => dialog.accept());
  await remove.click();
  await expect(evidence).toHaveCount(0);
  expect(attachmentDeletes).toBe(1);
  const draftSave = page.getByRole('button', { name: 'Save draft', exact: true });
  const lastDraftSave = page.locator('.appraisal-workflow-history time');
  let draftWrites = 0;
  page.on('request', request => {
    if (request.method() === 'PUT' && request.url().endsWith('/self-assessment')) draftWrites++;
  });
  await page.getByText('Appraisal instructions', { exact: true }).click();
  await expect(page.getByText(/100 entries|\/\s*100$/)).toHaveCount(0);
  await expect(draftSave).toBeDisabled();
  const firstGoal = page.getByLabel('Responsibility / goal description', { exact: true }).first();
  await expect(firstGoal).toHaveAttribute('maxlength', '500');
  await expect(page.getByLabel('Achievements and self-assessment', { exact: true }).first()).toHaveAttribute('maxlength', '1000');
  await expect(firstGoal).toHaveAccessibleDescription('500 of 500 characters remaining');
  await firstGoal.fill('Unsaved test edit');
  await expect(firstGoal).toHaveAccessibleDescription('483 of 500 characters remaining');
  await expect(draftSave).toBeEnabled();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Back to top', exact: true }).click();
  const appraisalStart = page.getByRole('button', { name: 'Back to my appraisals', exact: true });
  await expect(appraisalStart).toBeInViewport();
  await expect(appraisalStart).toBeFocused();
  await expect(firstGoal).toHaveValue('Unsaved test edit');
  await page.setViewportSize({ width: 1280, height: 844 });
  await firstGoal.fill('');
  await expect(draftSave).toBeDisabled();
  const addGoal = page.getByRole('button', { name: 'Add goal', exact: true });
  await expect(addGoal).toHaveText('+');
  await addGoal.click();
  const removeGoal = page.getByRole('button', { name: 'Remove goal 2', exact: true });
  await expect(removeGoal).toHaveText('−');
  await removeGoal.click();
  await expect(page.getByRole('group', { name: 'Goal 2', exact: true })).toHaveCount(0);
  for (let i = 0; i < 7; i++) {
    if (i > 0) await addGoal.click();
    await page.getByLabel('Responsibility / goal description', { exact: true }).nth(i).fill(`Goal ${i + 1}`);
    if (i < 6) await page.getByLabel('Achievements and self-assessment', { exact: true }).nth(i).fill(`Delivered result ${i + 1}`);
  }
  const addContribution = page.getByRole('button', { name: 'Add contribution', exact: true });
  await expect(addContribution).toHaveText('+');
  await addContribution.click();
  const removeContribution = page.getByRole('button', { name: 'Remove contribution 1', exact: true });
  await expect(removeContribution).toHaveText('−');
  await removeContribution.click();
  await expect(page.getByRole('group', { name: 'Contribution 1', exact: true })).toHaveCount(0);
  await addContribution.click();
  const contribution = page.getByRole('group', { name: 'Contribution 1', exact: true });
  const contributionArea = contribution.getByLabel('Contribution area', { exact: true });
  await expect(contributionArea).toHaveAttribute('maxlength', '500');
  await expect(contributionArea).toHaveAccessibleDescription('500 of 500 characters remaining');
  await expect(contribution.getByText('500 of 500 characters remaining', { exact: true })).toBeVisible();
  await expect(contribution.getByLabel('Achievements and self-assessment', { exact: true }))
    .toHaveAccessibleDescription('1000 of 1000 characters remaining');
  await contributionArea.fill('Additional contribution');
  await expect(contributionArea).toHaveAccessibleDescription('477 of 500 characters remaining');
  await page.route('**/self-assessment', route => route.fulfill({
    status: 409, json: { error: { message: 'Draft changed in another session.' } },
  }), { times: 1 });
  await draftSave.click();
  await expect(page.getByRole('alert')).toHaveText('Draft changed in another session.');
  await expect(page.getByText('Draft saved.', { exact: true })).toHaveCount(0);
  await expect(lastDraftSave).toHaveCount(0);
  await expect(draftSave).toBeEnabled();
  await draftSave.click();
  const confirmation = page.getByRole('status').filter({ hasText: 'Draft saved.' });
  await expect(confirmation).toBeInViewport();
  const toastPosition = await confirmation.evaluate(element => {
    const bounds = element.getBoundingClientRect();
    return {
      top: bounds.top,
      centerOffset: Math.abs(bounds.left + bounds.width / 2 - document.documentElement.clientWidth / 2),
    };
  });
  expect(toastPosition.top).toBeCloseTo(16);
  expect(toastPosition.centerOffset).toBeLessThanOrEqual(1);
  await expect(draftSave).toBeDisabled();
  expect(draftWrites).toBe(2);
  await expect(lastDraftSave).toHaveAttribute('datetime', /Z$/);
  const firstDraftSave = (await lastDraftSave.getAttribute('datetime'))!;
  await page.reload();
  await page.getByRole('button', { name: 'Open self-assessment', exact: true }).click();
  await expect(lastDraftSave).toHaveAttribute('datetime', firstDraftSave);
  await expect(page.getByLabel('Responsibility / goal description', { exact: true })).toHaveCount(7);
  await expect(draftSave).toBeDisabled();
  await page.locator('.appraisal-heading').scrollIntoViewIfNeeded();
  await page.screenshot({path:'../.local/phase4-employee.png'});
  await page.getByRole('button', { name: 'Save and review submission', exact: true }).click();
  await expect(page.getByText('7. Goal 7', { exact: true })).toBeVisible();
  expect(draftWrites).toBe(2);
  await page.getByRole('button', { name: 'Submit to reporting manager', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Enter a response or NA for each Achievements and development question.');
  const goalNarrative = page.getByRole('group', { name: 'Goal 7', exact: true })
    .getByLabel('Achievements and self-assessment', { exact: true });
  const contributionNarrative = page.getByRole('group', { name: 'Contribution 1', exact: true })
    .getByLabel('Achievements and self-assessment', { exact: true });
  await expect(goalNarrative).toHaveAttribute('aria-invalid', 'true');
  await expect(goalNarrative).toBeFocused();
  await expect(contributionNarrative).toHaveAttribute('aria-invalid', 'true');
  const development = page.locator('textarea[id^="development-"]');
  await expect(development).toHaveCount(6);
  await expect(page.locator('textarea[id^="development-"][aria-invalid="true"]')).toHaveCount(6);
  await expectDevelopmentFocusClearance();
  await goalNarrative.fill('NA');
  await contributionNarrative.fill('N/A');
  for (const field of await development.all()) await field.fill('NA');
  const support = page.getByLabel('Support requested to meet your development needs', { exact: true });
  await support.fill(' N ');
  await expect(support).toHaveAttribute('aria-invalid', 'true');
  await expect(support).toHaveAccessibleDescription(/Enter at least 2 characters/);
  await draftSave.click();
  await expect(confirmation).toBeVisible();
  await expect(draftSave).toBeDisabled();
  await page.getByRole('button', { name: 'Save and review submission', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Submit to reporting manager', exact: true })).toHaveCount(0);
  await expect(page.getByRole('alert')).toContainText('Use at least 2 characters');
  await support.fill('NA');
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.getByRole('button', { name: 'Save and review submission', exact: true }).click();
  await expect(lastDraftSave).not.toHaveAttribute('datetime', firstDraftSave);
  const submit = page.getByRole('button', { name: 'Submit to reporting manager', exact: true });
  let submissions = 0;
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/submit')) submissions++;
  });
  page.once('dialog', async dialog => {
    const message = dialog.message();
    await dialog.dismiss();
    expect(message).toContain('submit your self-assessment to Test Manager?');
    expect(message).toContain('Your responses will become read-only.');
  });
  await submit.click();
  await expect(page.getByRole('button', { name: 'Back to editing', exact: true })).toBeVisible();
  await expect(page.getByText('7. Goal 7', { exact: true })).toBeVisible();
  expect(submissions).toBe(0);
  page.once('dialog', dialog => dialog.accept());
  await submit.click();
  await expect(page.getByRole('status').filter({hasText:'submitted to your reporting manager'})).toBeVisible();
  expect(submissions).toBe(1);
  await expect(page.getByLabel('Responsibility / goal description', { exact: true }).first()).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Save draft', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'View workflow history', exact: true }).click();
  await expect(page.getByText('DRAFT → SUBMITTED', { exact: true })).toBeVisible();
  for (const name of ['Previous', 'Next']) {
    const button = page.getByRole('button', { name, exact: true });
    await expect(button).toBeDisabled();
    await expect(button).toHaveCSS('cursor', 'default');
  }
  await page.getByRole('button', { name: 'View submitted revision 1', exact: true }).click();
  await expect(page.getByText('This is the preserved copy of your submission.', { exact: false })).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
