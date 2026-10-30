import type { components } from './schema';

export type User = components['schemas']['UserResponse'];
export type Session = components['schemas']['SessionResponse'];
export type AccountSummary = components['schemas']['AccountSummary'];

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) {
    super(message);
  }
}

let csrfToken = '';
export function setCsrfToken(value: string) { csrfToken = value; }

export async function api<T>(path: string, method = 'GET', data?: unknown, extraHeaders: Record<string,string> = {}): Promise<T> {
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
    const body = await response.json().catch(() => null);
    const error = new ApiError(response.status, body?.error?.code ?? 'REQUEST_FAILED',
      body?.error?.message ?? 'The request could not be completed.', body?.error?.request_id);
    if (response.status === 401 && path !== '/auth/login' && path !== '/auth/me') {
      window.dispatchEvent(new Event('session-expired'));
    }
    throw error;
  }
  return response.status === 204 ? undefined as T : response.json();
}

export async function downloadFile(path: string, filename: string) {
  const response = await fetch(`/api/v1${path}`, {credentials:'same-origin',cache:'no-store'});
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('session-expired'));
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? 'Download failed. Please try again.');
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement('a'); anchor.href=url; anchor.download=filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
}
