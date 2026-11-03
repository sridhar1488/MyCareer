import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { setTimeout } from 'node:timers/promises';

// Own the process trees explicitly: Windows Python venv launchers create child interpreters.
const children = [];
const env = { ...process.env,
  // A valid disposable password for the application's 8–15 character policy.
  MI_E2E_PASSWORD: randomBytes(6).toString('base64url'),
  MI_E2E_RESET_TOKEN: randomBytes(48).toString('base64url') };
function start(args) {
  const child = spawn(process.execPath, args, { env, stdio: 'inherit', detached: process.platform !== 'win32' });
  children.push(child);
  return child;
}
function stop() {
  for (const child of children.reverse()) {
    if (child.exitCode !== null) continue;
    if (process.platform === 'win32') spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    else { try { process.kill(-child.pid, 'SIGTERM'); } catch { /* Already stopped. */ } }
  }
}
async function ready(url, child) {
  for (let attempt = 0; attempt < 120; attempt++) {
    if (child.exitCode !== null) throw new Error('Test server exited before readiness.');
    try { if ((await fetch(url)).ok) return; } catch { /* Wait for startup. */ }
    await setTimeout(250);
  }
  throw new Error('Test server did not become ready in 30 seconds.');
}
process.on('SIGTERM', () => { stop(); process.exit(1); });
process.on('SIGINT', () => { stop(); process.exit(1); });
let code = 1;
try {
  for (const url of ['http://127.0.0.1:8000/api/v1/health/live', 'http://127.0.0.1:5173']) {
    try { await fetch(url); throw new Error(`Port in use: ${new URL(url).port}. Stop that server before E2E testing.`); }
    catch (error) { if (!(error instanceof TypeError)) throw error; }
  }
  const api = start(['e2e/start-api.mjs']);
  await ready('http://127.0.0.1:8000/api/v1/health/ready', api);
  const web = start(['node_modules/vite/bin/vite.js', '--host', '127.0.0.1']);
  await ready('http://127.0.0.1:5173', web);
  const tests = start(['node_modules/@playwright/test/cli.js', 'test', ...process.argv.slice(2)]);
  code = await new Promise(resolve => tests.on('exit', status => resolve(status ?? 1)));
} catch (error) { console.error(error.message); }
finally { stop(); }
process.exit(code);
