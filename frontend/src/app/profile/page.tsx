'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAppStore } from '@/lib/store';
import { useAuth } from '@/hooks/useAuth';

/**
 * Profile page showing user information.
 */
export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  if (!user) return null;

  const initials = user.display_name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <div>
      <nav className="navbar">
        <a href="/inbox" className="navbar-brand">💬 Distributed Chat</a>
        <div className="navbar-links">
          <a href="/inbox" className="btn btn-ghost">Inbox</a>
          <a href="/sessions" className="btn btn-ghost">Sessions</a>
          <button onClick={logout} className="btn btn-ghost">Logout</button>
        </div>
      </nav>

      <div className="profile-container">
        <div className="profile-card glass-card">
          <div className="profile-avatar">{initials}</div>
          <h2 className="profile-name">{user.display_name}</h2>
          <p className="profile-email">{user.email}</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
            <a href="/sessions" className="btn btn-secondary" style={{ width: '100%' }}>
              Manage Sessions
            </a>
            <button
              onClick={logout}
              className="btn btn-danger"
              style={{ width: '100%' }}
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
