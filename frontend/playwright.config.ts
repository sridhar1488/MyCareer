import { randomBytes } from 'node:crypto';
import { defineConfig, devices } from '@playwright/test';

process.env.MI_E2E_PASSWORD ??= randomBytes(32).toString('base64url');
process.env.MI_E2E_RESET_TOKEN ??= randomBytes(48).toString('base64url');

export default defineConfig({
  testDir: './e2e', fullyParallel: false, workers: 1,
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
