import { apiRequest, ApiError } from '../api/client';

export const ROLE_PATHS = Object.freeze({ FARMER: '/farmer/dashboard', BUYER: '/buyer/dashboard',
  PROCESSOR: '/processor/dashboard', ADMIN: '/admin/dashboard' });

export async function fetchCurrentUser(token, signal) {
  const profile = await apiRequest('/auth/me', { token, signal });
  if (!profile || !Number.isInteger(profile.id) || !profile.name || !profile.email
      || !Object.hasOwn(ROLE_PATHS, profile.role) || profile.is_active !== true) {
    throw new ApiError('This account cannot access AgriRoute.', 401);
  }
  const { id, name, email, role, is_active } = profile;
  return { id, name, email, role, is_active };
}

export async function authenticate(email, password, signal) {
  const result = await apiRequest('/auth/login', { method: 'POST', authenticated: false,
    body: { email: email.trim(), password }, signal });
  if (typeof result.access_token !== 'string' || !result.access_token || result.token_type?.toLowerCase() !== 'bearer') {
    throw new ApiError('Unable to verify the sign-in response. Please try again.');
  }
  const user = await fetchCurrentUser(result.access_token, signal);
  return { token: result.access_token, user };
}

export async function registerAccount({ name, email, phone, role, password }, signal) {
  return apiRequest('/auth/register', {
    method: 'POST', authenticated: false,
    body: { name: name.trim(), email: email.trim(), phone: phone.trim() || null, role, password }, signal,
  });
}

export function tokenExpiry(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return Number.isFinite(payload.exp) ? payload.exp * 1000 : null;
  } catch { return null; }
}
