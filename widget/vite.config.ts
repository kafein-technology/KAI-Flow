import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import dts from "vite-plugin-dts";
import { libInjectCss } from "vite-plugin-lib-inject-css";
import tailwindcss from "@tailwindcss/vite";
import { createRequire } from "module";
import pkg from "./package.json";

const require = createRequire(import.meta.url);

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    libInjectCss(),
    dts({
      insertTypesEntry: true,
      rollupTypes: true,
    }),
  ],
  build: {
    outDir: "dist",
    lib: {
      entry: "src/index.ts",
      formats: ["es", "cjs"],
      fileName: (format) => (format === "es" ? "index.es.js" : "index.cjs"),
    },
    sourcemap: true,
    rollupOptions: {
      external: [
        "react",
        "react-dom",
        "react/jsx-runtime",
        ...Object.keys(pkg.dependencies || {}),
      ],
      output: {
        dir: "dist",
        assetFileNames: "[name][extname]",
        inlineDynamicImports: true,
        globals: {
          react: "React",
          "react-dom": "ReactDOM",
        },
      },
    },
  },
  resolve: {
    alias: {
      "decode-named-character-reference": require.resolve(
        "decode-named-character-reference"
      ),
      "hast-util-from-html-isomorphic": require.resolve(
        "hast-util-from-html-isomorphic"
      ),
    },
  },
});
