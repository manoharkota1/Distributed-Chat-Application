'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api/client';
import { useAuth } from '@/hooks/useAuth';

interface Session {
  id: string;
  device_info: string | null;
  created_at: string;
  expires_at: string;
}

/**
 * Sessions page — view and revoke active sessions/devices.
 */
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
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }
    loadSessions();
  }, [isAuthenticated, router, loadSessions]);

  const handleRevoke = async (sessionId: string) => {
    const res = await api.delete(`/users/me/sessions/${sessionId}`);
    if (!res.error) {
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const parseDeviceInfo = (info: string | null): string => {
    if (!info) return 'Unknown Device';
    // Extract browser name from user agent string
    if (info.includes('Chrome')) return '🌐 Chrome';
    if (info.includes('Firefox')) return '🦊 Firefox';
    if (info.includes('Safari')) return '🧭 Safari';
    if (info.includes('Edge')) return '🌊 Edge';
    return '🖥️ ' + info.slice(0, 40);
  };

  if (!isAuthenticated) return null;

  return (
    <div>
      <nav className="navbar">
        <a href="/inbox" className="navbar-brand">💬 Distributed Chat</a>
        <div className="navbar-links">
          <a href="/inbox" className="btn btn-ghost">Inbox</a>
          <a href="/profile" className="btn btn-ghost">Profile</a>
          <button onClick={logout} className="btn btn-ghost">Logout</button>
        </div>
      </nav>

      <div className="sessions-container">
        <h1 style={{
          fontSize: '1.5rem',
          fontWeight: 700,
          marginBottom: '8px',
          background: 'var(--accent-gradient)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}>
          Active Sessions
        </h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: '24px', fontSize: '0.9rem' }}>
          Manage your logged-in devices. Revoke any session to force a re-login.
        </p>

        {loading ? (
          <div className="loading-container">
            <div className="loading-spinner" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="session-card glass-card">
            <p style={{ color: 'var(--text-muted)' }}>No active sessions</p>
          </div>
        ) : (
          sessions.map((session) => (
            <div key={session.id} className="session-card glass-card">
              <div className="session-info">
                <h4>{parseDeviceInfo(session.device_info)}</h4>
                <p>Created: {formatDate(session.created_at)}</p>
                <p>Expires: {formatDate(session.expires_at)}</p>
              </div>
              <button
                className="btn btn-danger"
                onClick={() => handleRevoke(session.id)}
                style={{ padding: '8px 16px', fontSize: '0.8rem' }}
              >
                Revoke
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
