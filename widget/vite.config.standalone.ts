import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  define: {
    'process.env.NODE_ENV': '"production"'
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    lib: {
      entry: path.resolve(__dirname, "src/embed.tsx"),
      name: "KaiChat",
      fileName: (format) => `widget.${format}.js`,
      formats: ["iife"],
    },
    rollupOptions: {
      output: {
        assetFileNames: (assetInfo) => {
          if (assetInfo.name === 'style.css') return 'kai-chat.css';
          return assetInfo.name || '[name][extname]';
        },
      }
    },
  },
});
