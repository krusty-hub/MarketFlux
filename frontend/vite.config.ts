import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // envDir defaults to the project root (frontend/), which is correct for Render.
  // Do NOT set envDir to '../' — the parent .env won't exist in production.
})
