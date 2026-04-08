// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://f1-data.example.com',
  // データディレクトリへの参照用
  vite: {
    resolve: {
      alias: {
        '@data': '/Volumes/lyssr_workspace/2026_1_4/Motorsports-Visualised/data',
      },
    },
  },
});
