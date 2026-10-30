import { spawnSync, spawn } from 'node:child_process';
import { resolve } from 'node:path';

const backend = resolve('../backend');
const python = process.env.MI_PYTHON ?? resolve(backend, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
if (!process.env.MI_E2E_DATABASE_URL) throw new Error('Set MI_E2E_DATABASE_URL to an isolated *_e2e_test database.');
const env = { ...process.env, MI_ENVIRONMENT: 'test', MI_DATABASE_URL: process.env.MI_E2E_DATABASE_URL,
  MI_SECRET_KEY: 'e2e-only-secret-do-not-use-in-production-48', MI_COOKIE_SECURE: 'false',
  MI_ALLOWED_ORIGINS: '["http://127.0.0.1:5173"]', MI_LOGIN_ATTEMPTS: '100', MI_MIGRATION_DATABASE_URL: '' };
for (const args of [['-m', 'alembic', 'upgrade', 'head'], ['-m', 'tests.e2e_seed']]) {
  const result = spawnSync(python, args, { cwd: backend, env, stdio: 'inherit' });
  if (result.status !== 0) process.exit(result.status ?? 1);
}
const child = spawn(python, ['-m', 'uvicorn', 'app.main:create_app', '--factory', '--host', '127.0.0.1', '--port', '8000', '--no-proxy-headers'], { cwd: backend, env, stdio: 'inherit' });
process.on('SIGTERM', () => child.kill());
process.on('SIGINT', () => child.kill());
child.on('exit', code => process.exit(code ?? 0));
