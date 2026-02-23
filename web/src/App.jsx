import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import Sidebar from './components/Sidebar/Sidebar';
import Main from './components/Main/Main';
import LoginPage from './pages/Login/LoginPage';
import SharedChatView from './pages/SharedChat/SharedChatView';
import { useTranslation } from 'react-i18next';
import { useAuth } from './contexts/AuthContext';
import { supabase } from './lib/supabase';
import './App.css';

/**
 * Redirect to a URL, appending Supabase session tokens in the hash
 * for cross-origin session transfer (e.g., ginlix-auth on a different port).
 * Same-origin redirects work without tokens (shared localStorage).
 */
async function redirectWithTokens(url) {
  const isCrossOrigin = url.startsWith('http') && !url.startsWith(window.location.origin);
  if (isCrossOrigin && supabase) {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token && session?.refresh_token) {
      window.location.href = `${url}#access_token=${session.access_token}&refresh_token=${session.refresh_token}`;
      return;
    }
  }
  window.location.href = url;
}

/** Handles the OAuth redirect from Supabase — shows a spinner then redirects to /dashboard. */
function AuthCallback() {
  const { isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const { t: tAuth } = useTranslation();

  useEffect(() => {
    if (isLoggedIn) {
      // Check for redirect parameter (e.g., from ginlix-auth account pages)
      const params = new URLSearchParams(window.location.search);
      const redirectTo = params.get('redirect');
      if (redirectTo && (redirectTo.startsWith('/') || redirectTo.startsWith('http'))) {
        redirectWithTokens(redirectTo);
        return;
      }
      navigate('/dashboard', { replace: true });
    }
  }, [isLoggedIn, navigate]);

  return (
    <div className="flex items-center justify-center min-h-screen" style={{ backgroundColor: 'var(--color-bg-page)' }}>
      <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{tAuth('auth.signingIn')}</p>
    </div>
  );
}

/** Redirects to dashboard or a ?redirect= target after login. */
function RootRedirect() {
  const params = new URLSearchParams(window.location.search);
  const redirectTo = params.get('redirect');
  if (redirectTo && (redirectTo.startsWith('/') || redirectTo.startsWith('http'))) {
    redirectWithTokens(redirectTo);
    return null;
  }
  return <Navigate to="/dashboard" replace />;
}

function App() {
  const { isLoggedIn, isInitialized } = useAuth();
  const { t } = useTranslation();

  if (!isInitialized) {
    return (
        <div className="flex items-center justify-center min-h-screen" style={{ backgroundColor: 'var(--color-bg-page)' }}>
        <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/" element={isLoggedIn ? <RootRedirect /> : <LoginPage />} />
      <Route path="/callback" element={<AuthCallback />} />
      <Route path="/s/:shareToken" element={<SharedChatView />} />
      <Route path="/*" element={
        isLoggedIn ? (
          <div className="app-layout">
            <Sidebar />
            <main className="app-main">
              <Main />
            </main>
          </div>
        ) : (
          <Navigate to="/" replace />
        )
      } />
    </Routes>
  );
}

export default App;
