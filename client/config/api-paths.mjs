// One canonical local API prefix, shared by browser, Vite and container startup.
export function normalizePath(value, name, fallback = '') {
  const path = String(value || fallback).trim().replace(/^\/+|\/+$/g, '');
  if (!path) return '';
  if (path.split('/').some((part) => !/^[A-Za-z0-9._~-]+$/.test(part) || part === '.' || part === '..')) {
    throw new Error(`${name} must contain URL path segments, not a URL, query or fragment`);
  }
  return path;
}

function fullPrefix(value, name) {
  const path = normalizePath(value, name);
  if (!path) throw new Error(`${name} must be a non-empty URL path`);
  return `/${path}`;
}

export function resolveApiPaths(values = {}) {
  return { API_PREFIX: fullPrefix(values.API_PREFIX || '/kai/api/v1', 'API_PREFIX') };
}

// Development proxy aliases mirror the server's compatibility routes.
export function legacyApiProxyPrefixes(prefix) {
  return ['/api'].filter(alias => alias !== prefix);
}
