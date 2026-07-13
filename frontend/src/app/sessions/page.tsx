'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api/client';
import { useAuth } from '@/hooks/useAuth';

interface Session {
  id: string;
  device_info: string | null;
  ip_address: string | null;
  created_at: string;
  expires_at: string;
  last_activity: string | null;
  is_current: boolean;
}

export default function SessionsPage() {
  const router = useRouter();
  const { isAuthenticated, logout } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  const loadSessions = useCallback(async () => {
    const res = await api.get<Session[]>('/users/me/sessions');
    if (res.data) {
      setSessions(res.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleRevoke = async (sessionId: string, isCurrent: boolean) => {
    const res = await api.delete(`/users/me/sessions/${sessionId}`);
    if (!res.error) {
      if (isCurrent) {
        logout();
      } else {
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      }
    }
  };

  const handleRevokeAll = async () => {
    if (!confirm('Are you sure you want to revoke all sessions? This will log you out of all devices, including this one.')) {
      return;
    }
    const res = await api.post('/users/me/sessions/revoke-all', {});
    if (!res.error) {
      logout();
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const parseUA = (ua: string | null) => {
    if (!ua) return { browser: 'Unknown Browser', os: 'Unknown OS', icon: '💻' };
    
    let browser = 'Unknown Browser';
    let icon = '💻';
    if (ua.includes('Firefox')) {
      browser = 'Firefox';
      icon = '🦊';
    } else if (ua.includes('Chrome') && !ua.includes('Chromium')) {
      browser = 'Chrome';
      icon = '🌐';
    } else if (ua.includes('Safari') && !ua.includes('Chrome')) {
      browser = 'Safari';
      icon = '🧭';
    } else if (ua.includes('Edge')) {
      browser = 'Edge';
      icon = '🌊';
    } else if (ua.includes('Opera') || ua.includes('OPR')) {
      browser = 'Opera';
      icon = '⭕';
    }

    let os = 'Unknown OS';
    if (ua.includes('Windows')) os = 'Windows';
    else if (ua.includes('Macintosh') || ua.includes('Mac OS X')) os = 'macOS';
    else if (ua.includes('Linux')) os = 'Linux';
    else if (ua.includes('Android')) os = 'Android';
    else if (ua.includes('iPhone') || ua.includes('iPad')) os = 'iOS';

    return { browser, os, icon };
  };

  if (!isAuthenticated) return null;

  return (
    <div>
      <nav className="navbar">
        <Link href="/inbox" className="navbar-brand">
          <span className="app-mark">DC</span> Distributed Chat
        </Link>
        <div className="navbar-links">
          <Link href="/inbox" className="btn btn-ghost">Inbox</Link>
          <Link href="/profile" className="btn btn-ghost">Profile</Link>
          <button onClick={logout} className="btn btn-ghost">Logout</button>
        </div>
      </nav>

      <main className="settings-page" style={{ padding: '40px 20px', maxWidth: '1000px', margin: '0 auto' }}>
        <div className="settings-content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <header className="page-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <h1 style={{ fontSize: '28px', fontWeight: 800, marginBottom: '6px' }}>Active Sessions</h1>
              <p style={{ color: 'var(--ink-faint)', fontSize: '14px' }}>Manage your active devices and revoke access to sign out.</p>
            </div>
            {sessions.length > 0 && (
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleRevokeAll}
                style={{ padding: '8px 16px', fontSize: '14px', fontWeight: 600 }}
              >
                Revoke All Sessions
              </button>
            )}
          </header>

          {loading ? (
            <div className="loading-container">
              <div className="loading-spinner" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="settings-card" style={{ padding: '40px', textAlign: 'center' }}>
              <div className="empty-state">
                <div className="empty-state-icon" style={{ fontSize: '32px', marginBottom: '12px' }}>⌁</div>
                <h3>No active sessions</h3>
                <p>New sessions will appear here after you sign in.</p>
              </div>
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                gap: '20px',
                marginTop: '12px',
              }}
            >
              {sessions.map((session) => {
                const { browser, os, icon } = parseUA(session.device_info);
                return (
                  <div
                    key={session.id}
                    style={{
                      background: 'var(--surface)',
                      border: session.is_current ? '1.5px solid var(--accent)' : '1px solid var(--line)',
                      borderRadius: '16px',
                      padding: '20px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '16px',
                      boxShadow: 'var(--shadow-sm)',
                      position: 'relative',
                    }}
                  >
                    {session.is_current && (
                      <span
                        style={{
                          position: 'absolute',
                          top: '16px',
                          right: '16px',
                          background: 'var(--success-soft, #e6f9ed)',
                          color: 'var(--success, #17c964)',
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '4px 10px',
                          borderRadius: '20px',
                          border: '1px solid currentColor',
                        }}
                      >
                        ● Active now
                      </span>
                    )}

                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '32px' }}>{icon}</span>
                      <div>
                        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>{browser} on {os}</h3>
                        <p style={{ margin: 0, fontSize: '12px', color: 'var(--ink-faint)' }}>
                          IP: {session.ip_address || 'Unknown'}
                        </p>
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', borderTop: '1px solid var(--line)', paddingTop: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--ink-faint)' }}>First Login:</span>
                        <span style={{ fontWeight: 500 }}>{formatDate(session.created_at)}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--ink-faint)' }}>Last Active:</span>
                        <span style={{ fontWeight: 500 }}>{session.last_activity ? formatDate(session.last_activity) : 'N/A'}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--ink-faint)' }}>Expires:</span>
                        <span style={{ fontWeight: 500 }}>{formatDate(session.expires_at)}</span>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => handleRevoke(session.id, session.is_current)}
                      style={{ width: '100%', marginTop: 'auto', minHeight: '36px', fontSize: '13px', fontWeight: 600 }}
                    >
                      {session.is_current ? 'Revoke (Log out)' : 'Revoke Session'}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
