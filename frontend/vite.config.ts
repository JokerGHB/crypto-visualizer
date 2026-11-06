import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 固定使用 Vite 默认端口 5173，不做顺延。
    // strictPort=true：端口被占用时明确报错，便于立刻发现冲突，
    // 而不是静默换端口导致实际地址与文档不一致。
    port: 5173,
    strictPort: true,
    // 开发期用代理，避免跨域与环境差异；生产由 Nginx 反代
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 可视化组件较多，单 chunk 略大，拆分 vendor 便于缓存
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (
              id.includes('/vue/') ||
              id.includes('vue-router') ||
              id.includes('/pinia/')
            ) {
              return 'vue';
            }
            return 'vendor';
          }
          return undefined;
        },
      },
    },
  },
});