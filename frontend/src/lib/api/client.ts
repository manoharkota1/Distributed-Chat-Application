/**
 * Typed HTTP client with automatic 401 → refresh → retry handling.
 *
 * All API calls return the standard envelope: { data, error }.
 * On 401, the client automatically tries to refresh the access token
 * using the httpOnly refresh cookie, then retries the original request.
 */

export interface APIError {
  code: string;
  message: string;
}

export interface APIResponse<T = unknown> {
  data: T | null;
  error: APIError | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let accessToken: string | null = null;

/** Store the access token in memory (never localStorage for security). */
export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/** Get the current access token. */
export function getAccessToken(): string | null {
  return accessToken;
}

/** Attempt to refresh the access token using the refresh cookie. */
export async function refreshAccessToken(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include', // Send httpOnly cookie
    });

    if (!res.ok) return false;

    const body: APIResponse<{ access_token: string }> = await res.json();
    if (body.data?.access_token) {
      setAccessToken(body.data.access_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * Make an authenticated API request.
 *
 * Automatically attaches the Bearer token and handles 401 refresh.
 */
export async function apiRequest<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<APIResponse<T>> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (accessToken) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`;
  }

  let response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  // 401 → try refresh → retry
  if (response.status === 401 && accessToken) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`;
      response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
        credentials: 'include',
      });
    }
  }

  return response.json();
}

/** Convenience helpers */
export const api = {
  get: <T>(path: string) => apiRequest<T>(path),

  post: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(path: string) =>
    apiRequest<T>(path, { method: 'DELETE' }),
};
