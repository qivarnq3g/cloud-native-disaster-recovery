import svelte from '@astrojs/svelte';
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://dr.qivarn.id.vn',
  output: 'static',
  integrations: [svelte()],
});
