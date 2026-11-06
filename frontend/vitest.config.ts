import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vitest/config';

// 测试配置独立于 vite.config.ts：构建配置不该被测试选项污染
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.ts'],
    // CI 下输出 junit 供流水线收集；本地运行不生成文件
    reporters: process.env.CI ? ['default', 'junit'] : ['default'],
    outputFile: {
      junit: 'test-results.xml',
    },
  },
});