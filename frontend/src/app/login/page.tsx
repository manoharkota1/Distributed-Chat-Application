'use client';

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

/**
 * Login page with email/password authentication.
 */
export default function LoginPage() {
  const router = useRouter();
  const { login, loading, error } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const success = await login(email, password);
    if (success) {
      router.push('/inbox');
    }
  };

  return (
    <div className="auth-container">
      <aside className="auth-aside">
        <div className="auth-brand"><span className="app-mark">DC</span> Distributed Chat</div>
        <div className="auth-aside-content">
          <p className="eyebrow">Real-time collaboration</p>
          <h1>Thoughtful conversations, beautifully organised.</h1>
          <p>Stay connected with the people and teams that matter, from any device.</p>
        </div>
        <span className="auth-aside-note">Simple, secure, and always in sync.</span>
      </aside>
      <main className="auth-panel">
      <div className="auth-card">
        <div className="auth-header">
          <h2>Welcome back</h2>
          <p>Sign in to continue to your messages.</p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="input-group">
            <label className="input-label" htmlFor="login-email">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              className="input"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              className="input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={loading}
          >
            {loading ? (
              <span className="loading-spinner" aria-label="Signing in" />
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="auth-footer">
          Don&apos;t have an account?{' '}
          <Link href="/register" className="text-link">Create an account</Link>
        </div>
      </div>
      </main>
    </div>
  );
}
