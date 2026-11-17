import type { components } from './schema';

export type User = components['schemas']['UserResponse'];
export type Session = components['schemas']['SessionResponse'];
export type AccountSummary = components['schemas']['AccountSummary'];

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string,
    public fields: { field: string; message: string }[] = []) {
    super(message);
  }
}

let csrfToken = '';
let generation = 0;
let requestSequence = 0;
let lastSessionResponse = 0;
let deadline = 0;
let timer: number | undefined;
let expired = false;

export function setCsrfToken(value: string) {
  csrfToken = value;
  if (!value) {
    generation++;
    deadline = 0;
    expired = false;
    window.clearTimeout(timer);
  }
}

function expireSession() {
  if (expired) return;
  setCsrfToken('');
  expired = true;
  window.dispatchEvent(new Event('session-expired'));
}

export function expireSessionIfDue() {
  if (deadline && Date.now() >= deadline) expireSession();
  return expired;
}

function trackSession(headers: Headers | undefined, sequence: number) {
  const header = headers?.get('X-Session-Remaining-Ms');
  if (!header || sequence < lastSessionResponse) return;
  const milliseconds = Number(header);
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return;
  lastSessionResponse = sequence;
  deadline = Date.now() + milliseconds;
  window.clearTimeout(timer);
  timer = window.setTimeout(expireSessionIfDue, milliseconds);
}

const signedOutEndpoints = new Set([
  '/auth/login', '/auth/me', '/auth/csrf', '/auth/forgot-password', '/auth/complete-password-setup',
]);

function checkSession(path: string) {
  if (!signedOutEndpoints.has(path) && expireSessionIfDue()) {
    throw new ApiError(401, 'SESSION_EXPIRED', 'Your session has expired. Please sign in again.');
  }
}

export async function api<T>(path: string, method = 'GET', data?: unknown, extraHeaders: Record<string,string> = {}): Promise<T> {
  checkSession(path);
  const requestGeneration = generation;
  const sequence = ++requestSequence;
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method, credentials: 'same-origin', cache: 'no-store',
      headers: { ...(data ? { 'Content-Type': data instanceof Blob ? 'application/octet-stream' : 'application/json' } : {}), ...extraHeaders,
        ...(method !== 'GET' && csrfToken ? { 'X-CSRF-Token': csrfToken } : {}) },
      ...(data ? { body: data instanceof Blob ? data : JSON.stringify(data) } : {}),
    });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'We could not reach the service. Check your connection and try again.');
  }
  if (!response.ok) {
    if (requestGeneration === generation && !expired && response.status !== 401) trackSession(response.headers, sequence);
    const body = await response.json().catch(() => null);
    const error = new ApiError(response.status, body?.error?.code ?? 'REQUEST_FAILED',
      body?.error?.message ?? 'The request could not be completed.', body?.error?.request_id, body?.error?.field_errors);
    if (requestGeneration === generation && response.status === 401 && !signedOutEndpoints.has(path)) expireSession();
    throw error;
  }
  if (requestGeneration === generation) {
    if (path === '/auth/login' || path === '/auth/change-password') {
      generation++;
      expired = false;
    }
    if (!expired) trackSession(response.headers, sequence);
  }
  return response.status === 204 ? undefined as T : response.json();
}

export async function downloadFile(path: string, filename: string) {
  checkSession(path);
  const requestGeneration = generation;
  const sequence = ++requestSequence;
  const response = await fetch(`/api/v1${path}`, {credentials:'same-origin',cache:'no-store'});
  if (!response.ok) {
    if (requestGeneration === generation && response.status === 401) expireSession();
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? 'Download failed. Please try again.');
  }
  if (requestGeneration !== generation) return;
  trackSession(response.headers, sequence);
  const blob = await response.blob();
  if (requestGeneration !== generation || expireSessionIfDue()) return;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a'); anchor.href=url; anchor.download=filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
}
