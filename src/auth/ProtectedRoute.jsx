import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { ROLE_PATHS } from './service';

export default function ProtectedRoute() {
  const { user, loading, isAuthenticated } = useAuth();
  const { pathname } = useLocation();
  if (loading) return <div className="not-found" role="status">Checking your session…</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace/>;
  if (pathname.split('/')[1] !== user.role.toLowerCase()) return <Navigate to={ROLE_PATHS[user.role]} replace/>;
  return <Outlet/>;
}
