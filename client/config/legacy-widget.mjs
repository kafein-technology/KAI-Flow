// @kaifusion/widget 1.1.0 reads these browser fields at module initialization.
// They are output adapters only: deployments still configure just API_PREFIX.
export function legacyBrowserApiGlobals(prefix) {
  const separator = prefix.lastIndexOf('/');
  if (separator === 0) {
    // The published widget inserts a slash between its two fields. A dot
    // segment lets its browser requests resolve to a single-segment prefix.
    return { VITE_API_START: '.', VITE_API_VERSION_ONLY: prefix.slice(1) };
  }
  return {
    VITE_API_START: prefix.slice(1, separator),
    VITE_API_VERSION_ONLY: prefix.slice(separator + 1),
  };
}
