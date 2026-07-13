'use client';

import { useEffect, useState, useCallback, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api/client';
import { useAuth } from '@/hooks/useAuth';
import { useAppStore } from '@/lib/store';

interface Session {
  id: string;
  device_info: string | null;
  created_at: string;
  expires_at: string;
}

type ToastType = 'success' | 'error';
interface Toast {
  type: ToastType;
  message: string;
}

function getPasswordStrength(password: string): 'weak' | 'fair' | 'good' | 'strong' {
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  if (score <= 1) return 'weak';
  if (score <= 2) return 'fair';
  if (score <= 3) return 'good';
  return 'strong';
}

const strengthLabels = { weak: 'Weak', fair: 'Fair', good: 'Good', strong: 'Strong' };

/**
 * Full-featured profile settings page.
 *
 * Sections:
 *  1. Profile hero card (avatar, name, email, member since)
 *  2. Edit profile (display name)
 *  3. Change password (with strength indicator)
 *  4. Active sessions (with revoke)
 *  5. Danger zone (sign out)
 */
export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const setUser = useAppStore((s) => s.setUser);

  // ── Toast ──────────────────────────────────────────────────
  const [toast, setToast] = useState<Toast | null>(null);
  const showToast = (type: ToastType, message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4000);
  };

  // ── Edit profile ──────────────────────────────────────────
  const [editMode, setEditMode] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [profileSaving, setProfileSaving] = useState(false);

  // ── Change password ───────────────────────────────────────
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [showPasswords, setShowPasswords] = useState(false);

  // ── Sessions ──────────────────────────────────────────────
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);

  // ── Init ──────────────────────────────────────────────────

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name);
    }
  }, [user]);

  const loadSessions = useCallback(async () => {
    const res = await api.get<Session[]>('/users/me/sessions');
    if (res.data) setSessions(res.data);
    setSessionsLoading(false);
  }, []);

  useEffect(() => {
    if (isAuthenticated) loadSessions();
  }, [isAuthenticated, loadSessions]);

  if (!user) return null;

  const initials = user.display_name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  // ── Handlers ──────────────────────────────────────────────

  const handleProfileSave = async (e: FormEvent) => {
    e.preventDefault();
    if (!displayName.trim()) return;
    setProfileSaving(true);

    const res = await api.patch<{ id: string; email: string; display_name: string; created_at: string }>(
      '/users/me',
      { display_name: displayName.trim() }
    );

    if (res.error) {
      showToast('error', res.error.message);
    } else if (res.data) {
      setUser({ id: res.data.id, email: res.data.email, display_name: res.data.display_name });
      showToast('success', 'Profile updated successfully');
      setEditMode(false);
    }
    setProfileSaving(false);
  };

  const handlePasswordChange = async (e: FormEvent) => {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      showToast('error', 'New passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      showToast('error', 'Password must be at least 8 characters');
      return;
    }

    setPasswordSaving(true);
    const res = await api.post<{ message: string }>('/users/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });

    if (res.error) {
      showToast('error', res.error.message);
    } else {
      showToast('success', 'Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    }
    setPasswordSaving(false);
  };

  const handleRevokeSession = async (sessionId: string) => {
    const res = await api.delete(`/users/me/sessions/${sessionId}`);
    if (!res.error) {
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      showToast('success', 'Session revoked');
    }
  };

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  const parseDeviceInfo = (info: string | null): string => {
    if (!info) return 'Unknown Device';
    if (info.includes('Chrome')) return '🌐 Chrome';
    if (info.includes('Firefox')) return '🦊 Firefox';
    if (info.includes('Safari')) return '🧭 Safari';
    if (info.includes('Edge')) return '🌊 Edge';
    return '🖥️ ' + info.slice(0, 40);
  };

  const passwordStrength = newPassword ? getPasswordStrength(newPassword) : null;
  const passwordsMatch = confirmPassword.length > 0 && newPassword === confirmPassword;

  return (
    <div>
      {/* ── Navbar ─────────────────────────────────────── */}
      <nav className="navbar">
        <Link href="/inbox" className="navbar-brand">
          <span className="app-mark">DC</span> Distributed Chat
        </Link>
        <div className="navbar-links">
          <Link href="/inbox" className="btn btn-ghost">Inbox</Link>
          <Link href="/sessions" className="btn btn-ghost">Sessions</Link>
          <button onClick={logout} className="btn btn-ghost">Logout</button>
        </div>
      </nav>

      <main className="settings-page">
        <div className="settings-content">
          <header className="page-heading">
            <h1>Settings</h1>
            <p>Manage your profile, security, and active sessions.</p>
          </header>

          {/* ── Toast ──────────────────────────────────── */}
          {toast && (
            <div
              className={`settings-toast ${
                toast.type === 'success' ? 'settings-toast-success' : 'settings-toast-error'
              }`}
              role="alert"
            >
              <span>{toast.type === 'success' ? '✓' : '✕'}</span>
              <span>{toast.message}</span>
            </div>
          )}

          {/* ── 1. Profile Hero ────────────────────────── */}
          <section className="settings-section" id="profile-hero">
            <div className="settings-section-card">
              <div className="profile-hero">
                <div className="profile-hero-avatar">{initials}</div>
                <div className="profile-hero-info">
                  <h2 className="profile-hero-name">{user.display_name}</h2>
                  <p className="profile-hero-email">{user.email}</p>
                  <div className="profile-hero-meta">
                    <span className="profile-hero-badge">📧 Verified</span>
                    <span className="profile-hero-badge">
                      🕐 Member since {new Date().getFullYear()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* ── 2. Edit Profile ────────────────────────── */}
          <section className="settings-section" id="edit-profile">
            <div className="settings-section-card">
              <div className="settings-section-header">
                <div className="settings-section-icon">✏️</div>
                <div className="settings-section-title">
                  <h3>Profile Information</h3>
                  <p>Update your display name and identity</p>
                </div>
              </div>

              <form onSubmit={handleProfileSave}>
                <div className="settings-section-body">
                  <div className="settings-form">
                    <div className="input-group">
                      <label className="input-label" htmlFor="profile-email">
                        Email Address
                      </label>
                      <input
                        id="profile-email"
                        type="email"
                        className="input field-readonly"
                        value={user.email}
                        readOnly
                        tabIndex={-1}
                      />
                    </div>

                    <div className="input-group">
                      <label className="input-label" htmlFor="profile-name">
                        Display Name
                      </label>
                      <input
                        id="profile-name"
                        type="text"
                        className="input"
                        value={displayName}
                        onChange={(e) => {
                          setDisplayName(e.target.value);
                          if (!editMode) setEditMode(true);
                        }}
                        maxLength={100}
                        placeholder="Your display name"
                      />
                    </div>
                  </div>
                </div>

                {editMode && (
                  <div className="settings-section-footer">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        setDisplayName(user.display_name);
                        setEditMode(false);
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn btn-primary"
                      disabled={profileSaving || !displayName.trim() || displayName.trim() === user.display_name}
                    >
                      {profileSaving ? (
                        <span className="loading-spinner" aria-label="Saving" />
                      ) : (
                        'Save Changes'
                      )}
                    </button>
                  </div>
                )}
              </form>
            </div>
          </section>

          {/* ── 3. Change Password ─────────────────────── */}
          <section className="settings-section" id="change-password">
            <div className="settings-section-card">
              <div className="settings-section-header">
                <div className="settings-section-icon">🔒</div>
                <div className="settings-section-title">
                  <h3>Password</h3>
                  <p>Keep your account secure with a strong password</p>
                </div>
              </div>

              <form onSubmit={handlePasswordChange}>
                <div className="settings-section-body">
                  <div className="settings-form">
                    <div className="input-group">
                      <label className="input-label" htmlFor="current-password">
                        Current Password
                      </label>
                      <input
                        id="current-password"
                        type={showPasswords ? 'text' : 'password'}
                        className="input"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        placeholder="Enter current password"
                        required
                        autoComplete="current-password"
                      />
                    </div>

                    <div className="settings-form-row">
                      <div className="input-group">
                        <label className="input-label" htmlFor="new-password">
                          New Password
                        </label>
                        <input
                          id="new-password"
                          type={showPasswords ? 'text' : 'password'}
                          className="input"
                          value={newPassword}
                          onChange={(e) => setNewPassword(e.target.value)}
                          placeholder="Min. 8 characters"
                          required
                          minLength={8}
                          autoComplete="new-password"
                        />
                        {passwordStrength && (
                          <div className="password-strength">
                            <div className="password-strength-bar">
                              <div className={`password-strength-fill ${passwordStrength}`} />
                            </div>
                            <div className={`password-strength-label ${passwordStrength}`}>
                              {strengthLabels[passwordStrength]}
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="input-group">
                        <label className="input-label" htmlFor="confirm-password">
                          Confirm New Password
                        </label>
                        <input
                          id="confirm-password"
                          type={showPasswords ? 'text' : 'password'}
                          className="input"
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          placeholder="Re-enter new password"
                          required
                          minLength={8}
                          autoComplete="new-password"
                          style={
                            confirmPassword.length > 0
                              ? {
                                  borderColor: passwordsMatch ? '#15803d' : '#bd362f',
                                }
                              : undefined
                          }
                        />
                        {confirmPassword.length > 0 && (
                          <div
                            style={{
                              marginTop: 4,
                              fontSize: 12,
                              fontWeight: 600,
                              color: passwordsMatch ? '#15803d' : '#bd362f',
                            }}
                          >
                            {passwordsMatch ? '✓ Passwords match' : '✕ Passwords do not match'}
                          </div>
                        )}
                      </div>
                    </div>

                    <label
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 8,
                        cursor: 'pointer',
                        fontSize: 13,
                        color: 'var(--ink-soft)',
                        userSelect: 'none',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={showPasswords}
                        onChange={(e) => setShowPasswords(e.target.checked)}
                        style={{ accentColor: 'var(--accent)' }}
                      />
                      Show passwords
                    </label>
                  </div>
                </div>

                <div className="settings-section-footer">
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={
                      passwordSaving ||
                      !currentPassword ||
                      !newPassword ||
                      !confirmPassword ||
                      newPassword !== confirmPassword ||
                      newPassword.length < 8
                    }
                  >
                    {passwordSaving ? (
                      <span className="loading-spinner" aria-label="Saving" />
                    ) : (
                      'Update Password'
                    )}
                  </button>
                </div>
              </form>
            </div>
          </section>

          {/* ── 4. Active Sessions ─────────────────────── */}
          <section className="settings-section" id="active-sessions">
            <div className="settings-section-card">
              <div className="settings-section-header">
                <div className="settings-section-icon">📱</div>
                <div className="settings-section-title">
                  <h3>Active Sessions</h3>
                  <p>Devices where you&apos;re currently signed in</p>
                </div>
              </div>

              <div className="settings-section-body" style={{ padding: '0 22px' }}>
                {sessionsLoading ? (
                  <div className="loading-container" style={{ minHeight: 100 }}>
                    <div className="loading-spinner" />
                  </div>
                ) : sessions.length === 0 ? (
                  <div className="empty-state" style={{ minHeight: 100 }}>
                    <p style={{ margin: 0, color: 'var(--ink-faint)', fontSize: 14 }}>
                      No active sessions found.
                    </p>
                  </div>
                ) : (
                  sessions.map((session) => (
                    <div key={session.id} className="session-card">
                      <div className="session-info">
                        <h2>{parseDeviceInfo(session.device_info)}</h2>
                        <p>Created: {formatDate(session.created_at)}</p>
                        <p>Expires: {formatDate(session.expires_at)}</p>
                      </div>
                      <button
                        className="btn btn-danger"
                        onClick={() => handleRevokeSession(session.id)}
                      >
                        Revoke
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>

          {/* ── 5. Danger Zone ─────────────────────────── */}
          <section className="settings-section" id="danger-zone">
            <div className="settings-section-card danger-zone">
              <div className="settings-section-header">
                <div className="settings-section-icon">⚠️</div>
                <div className="settings-section-title">
                  <h3>Danger Zone</h3>
                  <p>Irreversible actions for your account</p>
                </div>
              </div>

              <div className="settings-section-footer">
                <span style={{ flex: 1, fontSize: 13, color: 'var(--ink-soft)' }}>
                  Sign out from this device
                </span>
                <button
                  onClick={async () => {
                    await logout();
                    router.push('/login');
                  }}
                  className="btn btn-danger"
                >
                  Sign Out
                </button>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
