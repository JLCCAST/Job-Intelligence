import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo (npm run dev, puerto 5173) las llamadas a la API van al
// servidor de Python en el 8000. En producción FastAPI sirve web/dist.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/recibir": "http://127.0.0.1:8000",
    },
  },
});
