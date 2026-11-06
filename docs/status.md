# 完成情况清单

逐项核对。状态说明：✅ 已完成并验证 · ⚠️ 部分完成 · ❌ 未做

---

## 一、功能需求

| 编号 | 需求 | 状态 | 证据 |
|---|---|---|---|
| F-01 | 用户注册与登录 | ✅ | `routers/auth.py`；pytest 6 项；E2E-16 |
| F-02 | 加解密参数配置 | ✅ | `Playground.vue`；支持文本/十六进制双模式 |
| F-03 | 字节替代可视化 | ✅ | `core/aes/rounds.py::sub_bytes`；含逆运算 |
| F-04 | 行移位可视化 | ✅ | `shift_rows`/`inv_shift_rows`，cells 含来源格 |
| F-05 | 列混合可视化 | ✅ | `mix_columns`，aux 含 xtime 中间量 |
| F-06 | 轮密钥加可视化 | ✅ | `add_round_key`，Step 携带 roundKey |
| F-07 | S 盒 / 逆 S 盒展示 | ✅ | `SBoxPanel.vue`；E2E-13~15 |
| F-08 | 状态矩阵动态动画 | ✅ | `StateMatrix.vue`，CSS 过渡 + 色阶 |
| F-09 | 密钥扩展可视化 | ✅ | `KeyScheduleView.vue`，四步明细可折叠 |
| F-10 | 播放控制 | ✅ | `PlayerControls.vue`；13 项状态机测试 |
| F-11 | AI 步骤讲解 | ✅ | `routers/ai.py`；E2E-24 |
| F-12 | AI 多轮对话 | ✅ | 保留最近 6 条；含停止/清空/重试 |
| F-13 | 算法历史记录 | ✅ | 保存/分页/回放/删除；E2E-18~20 |
| F-14 | 练习·步骤识别 | ✅ | 四选一，服务端判分 |
| F-15 | 练习·结果填写 | ✅ | 填空判分 |
| F-16 | 练习·参数调试 | ✅ | 指定轮次字节求值 |
| F-17 | 错题回跳 | ✅ | 返回 stepIndex，前端跳转动画 |
| F-18 | 接口文档 | ✅ | `/docs` 自动生成，可在线调试 |
| F-19 | 安全防护 | ✅ | 见第三节，全部实测通过 |
| F-20 | 部署与流水线 | ✅ | `docker-compose.yml`、`.github/workflows/ci.yml` |
| F-21 | 单格字节来源查询 | ✅ | 点击矩阵格显示 before/after/aux；E2E-09 |
| F-22 | 加解密联动 | ✅ | 切换模式自动填入上次输出 |

---

## 二、功能模块对照

| 模块 | 要求 | 状态 | 实现 |
|---|---|---|---|
| 模块 1 | 需求分析 | ✅ | `docs/requirement.md` |
| 模块 2 | 系统设计 | ✅ | `docs/design.md` |
| 模块 3 | 算法核心 | ✅ | 自研 AES，FIPS-197 对拍 51 项 |
| 模块 4 | 可视化 | ✅ | 6 个可视化组件 |
| 模块 5 | AI 智能体 | ✅ | 三段式提示词 + 流式 + 降级 |
| 模块 6 | 安全与合规 | ✅ | 见第三节 |
| 模块 7 | 测试 | ✅ | 139 项全绿，`docs/test-report.md` |
| 模块 8 | 部署 | ✅ | `docs/deploy.md`，Docker + Nginx |
| 模块 9 | 代码管理 | ✅ | Git 分支 + CI 流水线 |

---

## 三、安全要求实测

全部在运行中的服务上实测，非纸面声明。

| 项目 | 测试方法 | 实测结果 |
|---|---|---|
| XSS（用户名） | 提交 `<script>alert(1)</script>` | **422 拒绝** |
| XSS（AI 输出） | 前端文本插值 | 标签被转义，不执行 |
| CSRF | 令牌不存 Cookie | 跨站请求无法自动携带 → 免疫 |
| 非法 hex 输入 | 提交 32 位 `z` | **422** |
| 输入长度 | 提交 31 位密文 | **422** |
| 未鉴权访问 | 无令牌请求历史 | **401** |
| 越权读 | B 读 A 的记录 | **404**（不泄露存在性） |
| 越权删 | B 删 A 的记录 | **404** |
| 限流 | 1 分钟内连续 23 次 AI 请求 | 第 21 次起 **429** |
| CSP | 检查响应头 | `content-security-policy` 存在 |
| X-Frame-Options | 检查响应头 | `DENY` |
| nosniff | 检查响应头 | `nosniff` |
| 口令长度 | 注册 73 字节口令 | 明确拒绝，不静默截断 |
| 敏感字段 | 检查用户响应 | 不返回 `password_hash` |

---

## 四、测试

| 层次 | 用例数 | 结果 |
|---|---|---|
| 后端 pytest | 95 | 全通过 |
| 前端 Vitest | 19 | 全通过 |
| 端到端 Playwright | 25 | 全通过 |
| **合计** | **139** | **全通过** |

复现命令：

```bash
cd backend && pytest -q                    # 95 passed
cd frontend && pnpm test                   # 19 passed
cd frontend && node e2e/verify.mjs         # 25/25 passed（需前后端已启动）
```

---

## 五、交付物

| 类别 | 文件 | 状态 |
|---|---|---|
| 源码 | `backend/`、`frontend/` | ✅ |
| 需求文档 | `docs/requirement.md` | ✅ |
| 设计文档 | `docs/design.md` | ✅ |
| 部署文档 | `docs/deploy.md` | ✅ |
| 测试报告 | `docs/test-report.md` | ✅ |
| 数据契约 | `docs/contracts/trace.md` | ✅ |
| 说明文档 | `README.md` | ✅ |
| 容器化 | `docker-compose.yml`、两个 `Dockerfile`、`nginx.conf` | ✅ |
| CI/CD | `.github/workflows/ci.yml` | ✅ |
| 参考实现 | `verify/verify_aes.py`（独立对拍用） | ✅ |

---

## 六、未完成项与原因

| 项目 | 状态 | 原因 |
|---|---|---|
| Firefox / Safari 实测 | ❌ | 环境仅有 Chrome/Edge，已在风险中记录 |
| 移动端适配 | ❌ | 本期范围外 |
| Alembic 迁移 | ❌ | 单次交付无跨版本迁移需求，已在设计文档说明取舍 |
| Redis 限流 | ❌ | 单实例部署够用，多实例需替换，已记录 |
| DES / SM4 / RSA | ❌ | 选做项，本期聚焦 AES 深度 |

---

## 七、当前可运行状态

- 后端：`uvicorn app.main:app` 运行于 `127.0.0.1:8000`，`/api/health` 正常
- 前端：`pnpm dev` 运行于 `localhost:5173`，`/api` 代理连通
- 数据库：SQLite 自动建表，已有测试数据
- 生产构建：`pnpm build` 成功，产物约 140 KB（gzip 44 KB）

一键验证：

```bash
cd frontend && node e2e/verify.mjs
# ===== 结果：25/25 通过 =====
```