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

/**
 * Public environment variables are embedded when Next.js builds the frontend.
 * Keep local development local, but use the deployed API if a production build
 * was created without NEXT_PUBLIC_API_URL.
 */
const configuredApiBase = process.env.NEXT_PUBLIC_API_URL;
const isInvalidProductionLocalhost =
  process.env.NODE_ENV === 'production' &&
  /^https?:\/\/localhost(?::\d+)?\/?$/i.test(configuredApiBase || '');
const API_BASE =
  !isInvalidProductionLocalhost && configuredApiBase
    ? configuredApiBase
    : process.env.NODE_ENV === 'production'
      ? 'https://distributed-chat-application-u5v6.onrender.com'
      : 'http://localhost:8000';

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
  const url = `${API_BASE}/auth/refresh`;
  console.log(`[API Refresh Request] Sending POST ${url}`);
  try {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'include', // Send httpOnly cookie
    });

    try {
      const clonedRes = res.clone();
      const bodyText = await clonedRes.text();
      console.log(`[API Refresh Response] Status ${res.status}`, bodyText);
    } catch (logErr) {
      console.error('[API Log Error] Failed to log refresh response', logErr);
    }

    if (!res.ok) return false;

    const body: APIResponse<{ access_token: string }> = await res.json();
    if (body.data?.access_token) {
      setAccessToken(body.data.access_token);
      return true;
    }
    return false;
  } catch (error) {
    console.error(`[API Refresh Error] Failed to fetch: POST ${url}`, error);
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
  const url = `${API_BASE}${path}`;
  const method = options.method || 'GET';
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (accessToken) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`;
  }

  console.log(`[API Request] Sending: ${method} ${url}`, {
    method,
    url,
    headers: { ...headers, Authorization: accessToken ? 'Bearer [REDACTED]' : undefined }
  });

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include',
    });
  } catch (error) {
    console.error(`[API Network Error] Failed to fetch: ${method} ${url}`, error);
    return {
      data: null,
      error: {
        code: 'NETWORK_ERROR',
        message: error instanceof Error ? error.message : 'Network error or connection refused'
      }
    };
  }

  // Helper function to log response
  const logResponse = async (res: Response) => {
    try {
      const clonedRes = res.clone();
      const bodyText = await clonedRes.text();
      let parsedBody;
      try {
        parsedBody = JSON.parse(bodyText);
      } catch {
        parsedBody = bodyText;
      }
      console.log(`[API Response] Received: ${method} ${url} - Status ${res.status}`, {
        url,
        method,
        status: res.status,
        body: parsedBody
      });
    } catch (logErr) {
      console.error('[API Log Error] Failed to log response details', logErr);
    }
  };

  await logResponse(response);

  // 401 → try refresh → retry
  if (response.status === 401 && accessToken) {
    console.log('[API Auth] 401 Unauthorized, attempting token refresh...');
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      console.log('[API Auth] Refresh successful, retrying request...');
      if (accessToken) {
        (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`;
      }
      try {
        response = await fetch(url, {
          ...options,
          headers,
          credentials: 'include',
        });
        await logResponse(response);
      } catch (error) {
        console.error(`[API Network Error Retry] Failed to fetch: ${method} ${url}`, error);
        return {
          data: null,
          error: {
            code: 'NETWORK_ERROR',
            message: error instanceof Error ? error.message : 'Network error or connection refused'
          }
        };
      }
    }
  }

  try {
    return await response.json();
  } catch (parseErr) {
    console.error(`[API JSON Parse Error] Failed to parse response from ${url}:`, parseErr);
    return {
      data: null,
      error: {
        code: 'PARSE_ERROR',
        message: 'Failed to parse server response'
      }
    };
  }
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
