import { writeFileSync } from 'node:fs';
import { resolveApiPaths } from './config/api-paths.mjs';
import { legacyBrowserApiGlobals } from './config/legacy-widget.mjs';

const paths = resolveApiPaths(process.env);
const values = {
  VITE_BASE_PATH: process.env.VITE_BASE_PATH || '/kai',
  VITE_API_BASE_URL: process.env.VITE_API_BASE_URL ?? '//localhost:8000',
  API_PREFIX: paths.API_PREFIX,
  ...legacyBrowserApiGlobals(paths.API_PREFIX),
  VITE_KEYCLOAK_URL: process.env.VITE_KEYCLOAK_URL || '',
  VITE_KEYCLOAK_CLIENT_ID: process.env.VITE_KEYCLOAK_CLIENT_ID || '',
  VITE_KEYCLOAK_REALM: process.env.VITE_KEYCLOAK_REALM || '',
  VITE_APP_NAME: process.env.VITE_APP_NAME || 'KAI Flow',
  VITE_NODE_ENV: process.env.VITE_NODE_ENV || 'production',
  VITE_ENABLE_LOGGING: process.env.VITE_ENABLE_LOGGING || 'false',
  VITE_ENTERPRISE: process.env.VITE_ENTERPRISE || 'false',
};
const output = '// Runtime configuration - generated at container startup\n'
  + Object.entries(values).map(([key, value]) => `window.${key} = ${JSON.stringify(value)};`).join('\n') + '\n';
writeFileSync(process.argv[2] || '/app/dist/config.js', output);
