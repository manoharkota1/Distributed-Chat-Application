'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
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
    loadSessions();
  }, [loadSessions]);

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
        <Link href="/inbox" className="navbar-brand">
          <span className="app-mark">DC</span> Distributed Chat
        </Link>
        <div className="navbar-links">
          <Link href="/inbox" className="btn btn-ghost">Inbox</Link>
          <Link href="/profile" className="btn btn-ghost">Profile</Link>
          <button onClick={logout} className="btn btn-ghost">Logout</button>
        </div>
      </nav>

      <main className="settings-page">
        <div className="settings-content">
          <header className="page-heading">
            <h1>Active sessions</h1>
            <p>Manage your logged-in devices. Revoke a session to sign that device out.</p>
          </header>

        {loading ? (
          <div className="loading-container">
            <div className="loading-spinner" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="settings-card sessions-card">
            <div className="empty-state">
              <div className="empty-state-icon">⌁</div>
              <h3>No active sessions</h3>
              <p>New devices will appear here after you sign in.</p>
            </div>
          </div>
        ) : (
          <section className="settings-card sessions-card" aria-label="Active sessions">
          {sessions.map((session) => (
            <div key={session.id} className="session-card">
              <div className="session-info">
                <h2>{parseDeviceInfo(session.device_info)}</h2>
                <p>Created: {formatDate(session.created_at)}</p>
                <p>Expires: {formatDate(session.expires_at)}</p>
              </div>
              <button
                className="btn btn-danger"
                onClick={() => handleRevoke(session.id)}
              >
                Revoke
              </button>
            </div>
          ))}
          </section>
        )}
        </div>
      </main>
    </div>
  );
}
