'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAppStore } from '@/lib/store';

/**
 * Landing page — redirects to inbox if authenticated, login otherwise.
 */
export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated } = useAppStore();

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/inbox');
    }
  }, [isAuthenticated, router]);

  return (
    <div className="auth-container">
      <div className="loading-container">
        <div className="loading-spinner" />
      </div>
    </div>
  );
}
