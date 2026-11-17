import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import fs from 'node:fs';
import path from 'node:path';
import { resolveApiPaths, legacyApiProxyPrefixes } from './config/api-paths.mjs';
import { legacyBrowserApiGlobals } from './config/legacy-widget.mjs';

export default defineConfig(({ mode }) => {
  const env = {
    ...loadEnv(mode, path.resolve(import.meta.dirname, '..'), ['API_PREFIX', 'VITE_']),
    ...loadEnv(mode, import.meta.dirname, ['API_PREFIX', 'VITE_']),
    ...Object.fromEntries(Object.entries(process.env).filter(([key]) => key.startsWith('VITE_') || key === 'API_PREFIX')),
  };
  const source = fs.readFileSync(path.resolve(import.meta.dirname, 'public/config.js'), 'utf8');
  const defaults: Record<string, string> = {};
  for (const match of source.matchAll(/window\.(API_PREFIX|VITE_\w+)\s*=\s*"([^"\n]*)"/g)) {
    defaults[match[1]] = match[2];
  }
  const apiPaths = resolveApiPaths(env.API_PREFIX ? env : defaults);
  const overrides = {
    ...Object.fromEntries(Object.entries(env).filter(([key]) =>
      !/^VITE_(?:EXTERNAL_API_|API_START$|API_VERSION)/.test(key))),
    API_PREFIX: apiPaths.API_PREFIX,
    ...legacyBrowserApiGlobals(apiPaths.API_PREFIX),
  };
  const runtimeSource = source + '\n' + Object.entries(overrides)
    .filter(([key, value]) => (key === 'API_PREFIX' || key.startsWith('VITE_')) && value !== undefined)
    .map(([key, value]) => `window.${key} = ${JSON.stringify(value)};`).join('\n') + '\n';
  const basePath = (env.VITE_BASE_PATH || '/kai').replace(/\/?$/, '/');

  const sslKeyPath = path.resolve(import.meta.dirname, '../backend/cert/key.pem');
  const sslCertPath = path.resolve(import.meta.dirname, '../backend/cert/cert.pem');
  const hasSSL = fs.existsSync(sslKeyPath) && fs.existsSync(sslCertPath);
  const https = hasSSL ? {
    key: fs.readFileSync(sslKeyPath),
    cert: fs.readFileSync(sslCertPath),
  } : undefined;
  const apiBaseUrl = env.VITE_API_BASE_URL || 'http://localhost:8000';
  const proxyTarget = (!hasSSL && apiBaseUrl.includes('localhost'))
    ? apiBaseUrl.replace('https://', 'http://') : apiBaseUrl;

  return {
    base: basePath,
    define: { 'import.meta.env.API_PREFIX': JSON.stringify(apiPaths.API_PREFIX) },
    plugins: [react(), tailwindcss(), {
      name: 'kai-runtime-config',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url?.split('?')[0] === '/config.js' || req.url?.split('?')[0] === `${basePath}config.js`) {
            res.setHeader('Content-Type', 'application/javascript');
            res.setHeader('Cache-Control', 'no-store');
            res.end(runtimeSource);
          } else next();
        });
      },
      writeBundle(options) {
        fs.writeFileSync(path.resolve(options.dir || 'dist', 'config.js'), runtimeSource);
      },
    }],
    resolve: { tsconfigPaths: true },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      emptyOutDir: true,
      rollupOptions: { output: { manualChunks: undefined } },
    },
    server: {
      https,
      proxy: Object.fromEntries(
        [apiPaths.API_PREFIX, ...legacyApiProxyPrefixes(apiPaths.API_PREFIX)].map(prefix => [
          `^${prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:/|$)`,
          {
            target: proxyTarget.startsWith('//') ? `http:${proxyTarget}` : proxyTarget,
            changeOrigin: true,
            secure: false,
          },
        ]),
      ),
    },
    optimizeDeps: { include: ["@xyflow/react"] },
  };
});
