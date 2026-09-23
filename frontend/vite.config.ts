import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 构建产物输出到 ../backend/static，由 FastAPI 直接托管；
// 开发时 /api 代理到本机 8000 端口的后端。
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
