import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
window.scrollTo = vi.fn();
afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); localStorage.clear(); });
