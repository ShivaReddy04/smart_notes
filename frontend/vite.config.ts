import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Vite config for the AI Smart Notes SPA.
//   * react()      — Fast Refresh + JSX/TSX transform.
//   * tailwindcss() — Tailwind v4's first-party Vite plugin, so utility classes
//     work with zero PostCSS config (Tailwind is imported from src/index.css).
// The dev server runs on port 5173 (the origin allow-listed by the backend's
// CORS settings); the API base URL is injected via VITE_API_BASE_URL (.env).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
  },
})
