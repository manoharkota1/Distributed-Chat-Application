'use client';

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

/**
 * Registration page with email, password, and display name.
 */
export default function RegisterPage() {
  const router = useRouter();
  const { register, loading, error } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const success = await register(email, password, displayName);
    if (success) {
      router.push('/inbox');
    }
  };

  return (
    <div className="auth-container">
      <aside className="auth-aside">
        <div className="auth-brand"><span className="app-mark">DC</span> Distributed Chat</div>
        <div className="auth-aside-content">
          <p className="eyebrow">Built for focus</p>
          <h1>A calmer place to keep in touch.</h1>
          <p>Start a conversation, share an update, and keep every important message close at hand.</p>
        </div>
        <span className="auth-aside-note">Your conversations are ready when you are.</span>
      </aside>
      <main className="auth-panel">
      <div className="auth-card">
        <div className="auth-header">
          <h2>Create your account</h2>
          <p>Join the conversation in just a moment.</p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="input-group">
            <label className="input-label" htmlFor="reg-name">
              Display Name
            </label>
            <input
              id="reg-name"
              type="text"
              className="input"
              placeholder="John Doe"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              autoFocus
              maxLength={100}
            />
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="reg-email">
              Email
            </label>
            <input
              id="reg-email"
              type="email"
              className="input"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="reg-password">
              Password
            </label>
            <input
              id="reg-password"
              type="password"
              className="input"
              placeholder="Min. 8 characters"
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
              <span className="loading-spinner" aria-label="Creating account" />
            ) : (
              'Create Account'
            )}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account?{' '}
          <Link href="/login" className="text-link">Sign in</Link>
        </div>
      </div>
      </main>
    </div>
  );
}
