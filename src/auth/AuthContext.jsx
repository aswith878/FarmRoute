import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { authenticate, fetchCurrentUser, tokenExpiry } from './service';
import { clearToken, getToken, saveToken } from './tokenStorage';
import { SESSION_INVALID } from '../api/client';

const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [token, setToken] = useState(getToken);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const version = useRef(0);
  const activeToken = useRef(token);
  const inFlight = useRef(null);
  const loginController = useRef(null);

  const logout = useCallback((message = '') => {
    version.current += 1;
    loginController.current?.abort();
    inFlight.current = null;
    activeToken.current = null;
    clearToken();
    setToken(null); setUser(null); setLoading(false); setError(message);
  }, []);

  useEffect(() => {
    // Remove the old demo-role marker; it is never an authentication source.
    try { localStorage.removeItem('agriroute-role'); } catch { /* Storage unavailable. */ }
    const controller = new AbortController();
    const saved = getToken();
    const attempt = ++version.current;
    if (!saved) { setLoading(false); return () => controller.abort(); }
    setLoading(true);
    fetchCurrentUser(saved, controller.signal).then(profile => {
      if (attempt !== version.current || controller.signal.aborted) return;
      activeToken.current = saved; setToken(saved); setUser(profile); setError('');
    }).catch(error => {
      if (attempt !== version.current || controller.signal.aborted) return;
      logout(error.status === 401 ? 'Your session has expired. Please sign in again.' : error.message);
    }).finally(() => {
      if (attempt === version.current && !controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [logout]);

  useEffect(() => {
    const invalid = event => {
      if (event.detail?.token === activeToken.current) logout('Your session has expired. Please sign in again.');
    };
    window.addEventListener(SESSION_INVALID, invalid);
    return () => window.removeEventListener(SESSION_INVALID, invalid);
  }, [logout]);

  useEffect(() => {
    if (!user || !token) return;
    const expires = tokenExpiry(token);
    if (expires === null) return; // Server validation is authoritative.
    const expire = () => logout('Your session has expired. Please sign in again.');
    if (expires <= Date.now()) { expire(); return; }
    const timer = setTimeout(expire, Math.min(expires - Date.now(), 2147483647));
    // Background tabs may throttle timers: check again when they become visible.
    const visible = () => { if (expires <= Date.now()) expire(); };
    document.addEventListener('visibilitychange', visible);
    return () => { clearTimeout(timer); document.removeEventListener('visibilitychange', visible); };
  }, [user, token, logout]);

  const login = useCallback((email, password) => {
    if (inFlight.current) return inFlight.current;
    const attempt = ++version.current;
    const controller = new AbortController();
    loginController.current = controller;
    setLoading(true); setError('');
    const promise = authenticate(email, password, controller.signal).then(session => {
      if (attempt !== version.current || controller.signal.aborted) return null;
      saveToken(session.token);
      activeToken.current = session.token;
      setToken(session.token); setUser(session.user);
      return session.user;
    }).catch(error => {
      if (attempt === version.current && !controller.signal.aborted) {
        clearToken(); activeToken.current = null; setToken(null); setUser(null); setError(error.message);
      }
      throw error;
    }).finally(() => {
      if (attempt === version.current) { inFlight.current = null; setLoading(false); }
    });
    inFlight.current = promise;
    return promise;
  }, []);

  return <AuthContext.Provider value={{ user, token, isAuthenticated: Boolean(user && token), loading, error, login, logout }}>
    {children}
  </AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
