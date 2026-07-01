/**
 * Authentication hook.
 *
 * Handles login, register, logout, and token refresh.
 */

'use client';

import { useCallback, useState } from 'react';
import { api, setAccessToken } from '@/lib/api/client';
import { useAppStore } from '@/lib/store';
import { wsClient } from '@/lib/ws/socket';

interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export function useAuth() {
  const { user, isAuthenticated, setUser } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      setLoading(true);
      setError(null);

      const res = await api.post<AuthResponse>('/auth/register', {
        email,
        password,
        display_name: displayName,
      });

      if (res.error) {
        setError(res.error.message);
        setLoading(false);
        return false;
      }

      if (res.data) {
        setAccessToken(res.data.access_token);
        // Fetch user profile
        const profileRes = await api.get<{
          id: string;
          email: string;
          display_name: string;
        }>('/users/me');
        if (profileRes.data) {
          setUser(profileRes.data);
        }
        wsClient.connect();
      }

      setLoading(false);
      return true;
    },
    [setUser]
  );

  const login = useCallback(
    async (email: string, password: string) => {
      setLoading(true);
      setError(null);

      const res = await api.post<AuthResponse>('/auth/login', {
        email,
        password,
      });

      if (res.error) {
        setError(res.error.message);
        setLoading(false);
        return false;
      }

      if (res.data) {
        setAccessToken(res.data.access_token);
        const profileRes = await api.get<{
          id: string;
          email: string;
          display_name: string;
        }>('/users/me');
        if (profileRes.data) {
          setUser(profileRes.data);
        }
        wsClient.connect();
      }

      setLoading(false);
      return true;
    },
    [setUser]
  );

  const logout = useCallback(async () => {
    await api.post('/auth/logout');
    setAccessToken(null);
    setUser(null);
    wsClient.disconnect();
  }, [setUser]);

  return { user, isAuthenticated, loading, error, register, login, logout };
}
