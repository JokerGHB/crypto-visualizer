# 前端 · 密码学算法可视化教学平台

Vue 3 + TypeScript + Vite。所有可视化数据来自后端 `Trace`，前端不做算法计算。

## 目录说明

```
src/
├── api/          # 接口封装（含 SSE 流式解析）
├── components/   # 可视化与控件组件
├── views/        # 页面
├── stores/       # Pinia：player（播放状态机）· auth
├── types/        # Trace 契约的 TS 镜像
├── router/
└── style.css     # 全局重置（具体样式在各组件 scoped 中）
e2e/verify.mjs    # Playwright 端到端验证
```

## 命令

```bash
pnpm install       # 安装依赖
pnpm dev           # 开发服务器 http://localhost:5173
pnpm typecheck     # 类型检查
pnpm test          # 单元测试（Vitest，19 项）
pnpm build         # 生产构建
pnpm preview       # 预览构建产物
node e2e/verify.mjs  # 端到端验证（25 项，需前后端已启动）
```

## 开发约定

- **不在前端重算算法**。任何加解密结果、中间状态、判分结论都来自后端。
- **十六进制统一小写、无 `0x`、无空格**，状态矩阵按列主序 `flat[4*c+r]`。
- **接口错误统一抛 `ApiError`**，页面负责转成中文提示。
- **定时器必须清理**：`usePlayerStore` 的 `dispose()` 在组件卸载时调用。

## 后端地址

默认走相对路径 `/api`，由 Vite 代理到 `127.0.0.1:8000`（见 `vite.config.ts`）。
前后端分离部署时设置环境变量：

```bash
VITE_API_BASE_URL=https://api.example.com pnpm build
```

## 端到端验证

`e2e/verify.mjs` 使用系统已安装的 Chrome（`channel: 'chrome'`），不下载 Playwright 自带浏览器，适配内网环境。

```bash
# 需先启动后端 :8000 与前端 :5173
node e2e/verify.mjs
# ===== 结果：25/25 通过 =====
```

截图输出在 `e2e/screenshots/`（已在 `.gitignore` 中排除）。