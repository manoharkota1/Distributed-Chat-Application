'use client';

import React, { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAppStore } from '@/lib/store';
import { api, refreshAccessToken } from '@/lib/api/client';
import { wsClient } from '@/lib/ws/socket';

const PUBLIC_PATHS = ['/login', '/register'];

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, setUser } = useAppStore();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    async function restoreSession() {
      if (isAuthenticated) {
        setChecking(false);
        return;
      }

      const hasSession = typeof window !== 'undefined' && localStorage.getItem('has_session') === 'true';
      if (!hasSession) {
        setChecking(false);
        return;
      }

      try {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          const res = await api.get<{ id: string; email: string; display_name: string }>('/users/me');
          if (res.data) {
            setUser(res.data);
            wsClient.connect();
            localStorage.setItem('has_session', 'true');
          } else {
            localStorage.removeItem('has_session');
          }
        } else {
          localStorage.removeItem('has_session');
        }
      } catch (err) {
        console.error('[SessionProvider] Error restoring session:', err);
        localStorage.removeItem('has_session');
      } finally {
        setChecking(false);
      }
    }

    restoreSession();
  }, [isAuthenticated, setUser]);

  // Route protection rules after session recovery completes
  useEffect(() => {
    if (checking) return;

    const isPublicPath = PUBLIC_PATHS.includes(pathname);

    if (isAuthenticated) {
      // Authenticated users should not access public login/register routes
      if (isPublicPath) {
        router.replace('/inbox');
      }
    } else {
      // Unauthenticated users should not access protected routes
      if (!isPublicPath) {
        router.replace('/login');
      }
    }
  }, [checking, isAuthenticated, pathname, router]);

  const isPublicPath = PUBLIC_PATHS.includes(pathname) || pathname === '/';

  // Prevent flash of content during initial auth validation on protected routes only
  if (checking && !isPublicPath) {
    return (
      <div className="auth-container" style={{ display: 'grid', placeItems: 'center', height: '100vh' }}>
        <div className="loading-container">
          <div className="loading-spinner" />
          <p style={{ marginTop: 12, color: 'var(--ink-soft)', fontSize: 14 }}>Restoring session...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
