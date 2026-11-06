// This builds a static frontend and sends local API requests to the Python engine.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': process.env.PARABLE_API || 'http://127.0.0.1:8000', '/world': process.env.PARABLE_API || 'http://127.0.0.1:8000' } },
});
