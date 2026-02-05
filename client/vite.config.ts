import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import svgr from "vite-plugin-svgr";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";
import fs from 'fs';
import path from 'path';

// Helper to read constants from public/config.js
const readConfig = () => {
  const configPath = path.resolve(__dirname, 'public/config.js');
  if (!fs.existsSync(configPath)) return { API_START: 'api', API_VERSION: 'v1' };
  const content = fs.readFileSync(configPath, 'utf8');
  const apiStartMatch = content.match(/window\.VITE_API_START\s*=\s*"(.*?)"/);
  const apiVersionMatch = content.match(/window\.VITE_API_VERSION_ONLY\s*=\s*"(.*?)"/);
  return {
    API_START: apiStartMatch ? apiStartMatch[1] : 'api',
    API_VERSION: apiVersionMatch ? apiVersionMatch[1] : 'v1'
  };
};

const { API_START, API_VERSION } = readConfig();

const isDev = process.env.NODE_ENV !== 'production';
const basePath = process.env.VITE_BASE_PATH || '/kai';

// Resolve SSL certs
const sslKeyPath = path.resolve(__dirname, '../backend/cert/key.pem');
const sslCertPath = path.resolve(__dirname, '../backend/cert/cert.pem');
const hasSSL = fs.existsSync(sslKeyPath) && fs.existsSync(sslCertPath);
const httpsConfig = hasSSL ? {
  key: fs.readFileSync(sslKeyPath),
  cert: fs.readFileSync(sslCertPath),
} : undefined;
const apiBaseUrl = process.env.VITE_API_BASE_URL || 'http://localhost:8000';
// Auto-downgrade to http if no SSL certs are found for local dev
const proxyTarget = (!hasSSL && apiBaseUrl.includes('localhost'))
  ? apiBaseUrl.replace('https://', 'http://')
  : apiBaseUrl;

export default defineConfig({
  base: basePath,
  plugins: [react(), svgr(), tailwindcss(), tsconfigPaths()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    emptyOutDir: true,
    // Static build için optimize edilmiş ayarlar
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
  server: {
    https: httpsConfig,
    ...(isDev && {
      proxy: {
        [`/${API_START}/kai`]: {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(new RegExp(`^/${API_START}/kai`), ''),
          secure: false,
          configure: (proxy, options) => {
            proxy.on('error', (err, req, res) => {
              console.log('proxy error', err);
            });
            proxy.on('proxyReq', (proxyReq, req, res) => {
              console.log('Sending Request to the Target:', req.method, req.url);
            });
            proxy.on('proxyRes', (proxyRes, req, res) => {
              console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
            });
          },
        },
      },
    }),
  },
  optimizeDeps: {
    include: ["@xyflow/react"],
  },
});