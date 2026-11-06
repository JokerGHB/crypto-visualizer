import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 默认 5173 及相邻端口常被本机其他桌面程序占用（实测 5173、5180-5183 均被占），
    // 故改用 5200。strictPort 保持 true：端口被占时明确报错，
    // 避免静默顺延导致实际地址与文档不符、每次都要猜端口。
    port: 5200,
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