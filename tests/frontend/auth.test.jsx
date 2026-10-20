import React, { StrictMode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import App from '../../src/App';
import { AuthProvider, useAuth } from '../../src/auth/AuthContext';
import { StoreProvider } from '../../src/hooks/useStore';
import { API_BASE_URL } from '../../src/api/config';
import { apiRequest, SESSION_INVALID } from '../../src/api/client';
import { getToken, saveToken } from '../../src/auth/tokenStorage';

// Disposable generated test values only; no demo credentials or real tokens.
const password = () => crypto.randomUUID();
const token = (seconds = 1800) => `${btoa('{}')}.${btoa(JSON.stringify({ exp: Math.floor(Date.now()/1000)+seconds }))}.${crypto.randomUUID()}`;
const roleRequests = {
  FARMER: ['/produce', '/transactions', '/alternative-allocations', '/routing-cases'],
  BUYER: ['/produce', '/buyer-requirements', '/transactions'],
  PROCESSOR: ['/processor-requirements', '/alternative-allocations', '/routing-cases'],
  ADMIN: ['/produce', '/transactions', '/alternative-allocations', '/users'],
};
let profile, accessToken, requests;
function reply(data, status = 200) { return new Response(JSON.stringify(data), { status, headers: { 'Content-Type':'application/json' } }); }
function Location() { return <output data-testid="location">{useLocation().pathname}</output>; }
function mount(path='/login', strict=false) {
  const tree = <MemoryRouter initialEntries={[path]}><AuthProvider><StoreProvider><App/><Location/></StoreProvider></AuthProvider></MemoryRouter>;
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
}
async function fillAndSubmit() {
  await userEvent.type(await screen.findByLabelText('Email'),profile.email);
  await userEvent.type(screen.getByLabelText('Password'),password());
  await userEvent.click(screen.getByRole('button',{name:'Sign in'}));
}
beforeEach(() => {
  profile = { id:1, name:'Authenticated Farmer', email:'generated@example.test', role:'FARMER', is_active:true };
  accessToken = token(); requests=[];
  vi.stubGlobal('fetch',vi.fn(async (url,options) => {
    const path = new URL(url).pathname;
    requests.push({path,options});
    if (path==='/auth/login') return reply({access_token:accessToken,token_type:'bearer',expires_in:1800});
    if (path==='/auth/me') return reply(profile);
    if (['/produce','/buyer-requirements','/processor-requirements','/transactions','/alternative-allocations','/routing-cases','/users'].includes(path)) return reply([]);
    throw new Error('Unexpected dashboard API call');
  }));
});

describe('Real API client and React authentication flow', () => {
  it.each(['FARMER','BUYER','PROCESSOR','ADMIN'])('redirects %s from the backend profile, regardless of selected card', async role => {
    profile={...profile,role,name:`Authenticated ${role}`};
    mount();
    await userEvent.click(await screen.findByRole('button',{name:/Farmer List, match/}));
    expect(screen.getByTestId('location').textContent).toBe('/login');
    await fillAndSubmit();
    await waitFor(()=>expect(screen.getByTestId('location').textContent).toBe(`/${role.toLowerCase()}/dashboard`));
    expect(screen.getByText(profile.name)).toBeTruthy();
    expect(getToken()).toBe(accessToken);
    await waitFor(() => expect(requests.filter(r=>r.path!=='/auth/login'&&r.path!=='/auth/me').length).toBe(roleRequests[role].length));
    expect(requests.filter(r=>r.path!=='/auth/login'&&r.path!=='/auth/me').map(r=>r.path).sort()).toEqual([...roleRequests[role]].sort());
    expect(requests[1].options.headers.get('Authorization')).toBe(`Bearer ${accessToken}`);
    expect(requests[0].options.headers.has('Authorization')).toBe(false);
    expect(requests.filter(r=>roleRequests[role].includes(r.path)).every(r=>r.options.headers.get('Authorization')===`Bearer ${accessToken}`)).toBe(true);
  });

  it('shows invalid credentials and leaves no session', async () => {
    fetch.mockResolvedValue(reply({},401)); mount(); await fillAndSubmit();
    expect((await screen.findByRole('alert')).textContent).toContain('Invalid email or password');
    expect(getToken()).toBeNull();
    expect(screen.getByTestId('location').textContent).toBe('/login');
  });

  it('shows network failures safely', async () => {
    fetch.mockRejectedValue(new TypeError('Network failed')); mount(); await fillAndSubmit();
    expect((await screen.findByRole('alert')).textContent).toContain('Unable to reach AgriRoute');
    expect(screen.getByLabelText('Password').value).toBe('');
  });

  it('disables controls and suppresses duplicate submissions', async () => {
    let finish;
    fetch.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
    mount();
    await userEvent.type(await screen.findByLabelText('Email'),profile.email);
    await userEvent.type(screen.getByLabelText('Password'),password());
    const form=screen.getByRole('form',{name:'Account sign in'});
    fireEvent.submit(form); fireEvent.submit(form);
    expect(screen.getByRole('button',{name:'Signing in…'}).disabled).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(1);
    await act(async()=>finish(reply({access_token:accessToken,token_type:'bearer'})));
    await waitFor(()=>expect(screen.getByTestId('location').textContent).toBe('/farmer/dashboard'));
  });

  it('restores a valid session on refresh, including StrictMode', async () => {
    saveToken(accessToken);
    mount('/farmer/dashboard',true);
    expect(await screen.findByText(profile.name)).toBeTruthy();
    expect(requests.some(r=>r.path==='/auth/me')).toBe(true);
    expect(requests.some(r=>r.path==='/produce')).toBe(true);
    expect(screen.getByTestId('location').textContent).toBe('/farmer/dashboard');
  });

  it('clears an invalid stored token and redirects', async () => {
    saveToken(accessToken); fetch.mockResolvedValue(reply({},401)); mount('/farmer/dashboard');
    await waitFor(()=>expect(screen.getByTestId('location').textContent).toBe('/login'));
    expect(getToken()).toBeNull();
    expect((await screen.findByRole('alert')).textContent).toContain('session has expired');
  });

  it('clears an expired session even when a stale me response succeeds', async () => {
    saveToken(token(-30)); mount('/farmer/dashboard');
    await waitFor(()=>expect(screen.getByTestId('location').textContent).toBe('/login'));
    expect(getToken()).toBeNull();
  });

  it.each(['/farmer/dashboard','/buyer/requirements','/processor/rerouted-produce','/admin/dashboard','/farmer/missing'])('guards unauthenticated %s', async path => {
    localStorage.setItem('agriroute-role','"admin"'); mount(path);
    await waitFor(()=>expect(screen.getByTestId('location').textContent).toBe('/login'));
    expect(fetch).not.toHaveBeenCalled();
    expect(localStorage.getItem('agriroute-role')).toBeNull();
  });

  it.each(['FARMER','BUYER','PROCESSOR','ADMIN'])('restricts %s to its own workspace', async role => {
    profile={...profile,role}; saveToken(accessToken);
    mount(role==='FARMER' ? '/buyer/dashboard' : '/farmer/dashboard');
    await waitFor(()=>expect(screen.getByTestId('location').textContent).toBe(`/${role.toLowerCase()}/dashboard`));
  });

  it('logs out using the existing workspace control and preserves local inventory', async () => {
    localStorage.setItem('agriroute-requirements','[]');
    saveToken(accessToken); mount('/farmer/dashboard');
    const links=await screen.findAllByRole('link',{name:'Log out'});
    await userEvent.click(links[0]);
    await waitFor(()=>expect(screen.getByTestId('location').textContent).toBe('/login'));
    expect(getToken()).toBeNull();
    expect(localStorage.getItem('agriroute-requirements')).toBe('[]');
    expect(requests.some(r=>r.path==='/auth/me')).toBe(true);
    expect(requests.some(r=>r.path==='/produce')).toBe(true);
  });

  it('rejects inactive profiles and does not persist the login token', async () => {
    profile.is_active=false; mount(); await fillAndSubmit();
    expect((await screen.findByRole('alert')).textContent).toContain('cannot access');
    expect(getToken()).toBeNull();
  });

  it('rejects unsupported profile roles instead of trusting a role card', async () => {
    profile.role='__proto__'; mount(); await fillAndSubmit();
    expect((await screen.findByRole('alert')).textContent).toContain('cannot access');
    expect(getToken()).toBeNull();
  });

  it('does not persist the token if me fails after successful login', async () => {
    fetch.mockImplementation(async url=>new URL(url).pathname==='/auth/login'
      ? reply({access_token:accessToken,token_type:'bearer'}) : reply({},401));
    mount(); await fillAndSubmit();
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(getToken()).toBeNull();
  });

  it('expires the active session when an authenticated API request returns 401', async () => {
    saveToken(accessToken); mount('/farmer/dashboard'); await screen.findByText(profile.name);
    fetch.mockResolvedValueOnce(reply({},401));
    await act(async()=>{await apiRequest('/auth/me').catch(()=>{});});
    await waitFor(()=>expect(screen.getByTestId('location').textContent).toBe('/login'));
    expect(getToken()).toBeNull();
  });

  it('ignores a stale request failure from a different token', async () => {
    saveToken(accessToken); mount('/farmer/dashboard'); await screen.findByText(profile.name);
    act(()=>window.dispatchEvent(new CustomEvent(SESSION_INVALID,{detail:{token:token()}})));
    expect(getToken()).toBe(accessToken);
    expect(screen.getByTestId('location').textContent).toBe('/farmer/dashboard');
  });

  it('shares one login promise across callers and prevents a late response restoring a logged-out user', async () => {
    let context,finish;
    function Probe(){context=useAuth();return <output>{String(context.isAuthenticated)}</output>;}
    render(<AuthProvider><Probe/></AuthProvider>);
    await waitFor(()=>expect(context.loading).toBe(false));
    fetch.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
    let first,second;
    act(()=>{first=context.login(profile.email,password());second=context.login(profile.email,password());});
    expect(first).toBe(second);
    act(()=>context.logout());
    await act(async()=>{finish(reply({access_token:accessToken,token_type:'bearer'}));await first;});
    expect(context.isAuthenticated).toBe(false);
    expect(getToken()).toBeNull();
  });

  it('uses centralized configuration for every request', async () => {
    await apiRequest('/auth/login',{authenticated:false,method:'POST',body:{email:profile.email,password:password()}});
    expect(new URL(fetch.mock.calls[0][0]).origin).toBe(new URL(API_BASE_URL).origin);
  });
});
