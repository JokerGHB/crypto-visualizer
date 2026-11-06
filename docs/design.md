# 系统设计文档

**项目名称**：密码学算法可视化教学与 AI 辅导平台
**文档版本**：v1.0

---

## 1. 总体架构

前后端分离的 B/S 架构，分为表示层、应用层、数据层与支撑层。

```
┌────────────────────────── 浏览器（表示层）──────────────────────────┐
│  Vue 3 + TypeScript SPA                                             │
│   ├─ 可视化层   StateMatrix / SBoxPanel / KeyScheduleView            │
│   ├─ 播放控制器 Pinia player store（游标状态机）                     │
│   ├─ 业务页面   Playground / Exercise / History / Login              │
│   └─ AI 面板    AiTutorPanel（SSE 流式渲染）                         │
└───────────────────────────────┬─────────────────────────────────────┘
                     HTTPS / REST + SSE（JSON）
┌───────────────────────────────┴─────────────────────────────────────┐
│                     FastAPI 应用（应用层）                           │
│   ├─ 认证鉴权    JWT（python-jose）+ bcrypt 口令散列                  │
│   ├─ 算法引擎    app/core/aes/（自研 AES，产出 Trace）               │
│   ├─ 业务服务    history / exercise / ai                            │
│   ├─ AI 网关     Provider 适配 · 提示词组装 · 降级 · 限流            │
│   └─ 中间件      CORS · 安全响应头 · 统一异常                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ SQLModel / SQLAlchemy
                   ┌────────────┴────────────┐
                   │  SQLite（开发）          │
                   │  MySQL 8（生产）         │
                   └─────────────────────────┘
支撑层：Git 代码托管 · CI/CD 流水线
```

---

## 2. 技术栈

| 层次 | 选型 | 说明 |
|---|---|---|
| 前端框架 | Vue 3 + Vite + TypeScript | 选型理由：生态成熟，组件化便于拆分可视化视图 |
| 状态管理 | Pinia | 播放游标与用户态 |
| 可视化 | CSS Grid + DOM（主）、SVG 思路 | 见 §5.1 设计决策 |
| 后端 | FastAPI + Uvicorn + Pydantic v2 | 项目选型 |
| ORM | SQLModel | 模型即校验模型 |
| 数据库 | SQLite / MySQL 8 | 开发用 SQLite 免依赖，生产可切 MySQL |
| 认证 | JWT + bcrypt（直调，不用 passlib） | 见 §5.5 |
| AI | OpenAI 兼容 HTTP 流式接口 + 适配层 | 不绑定厂商 |
| 测试 | pytest / httpx / Vitest / Playwright | 后端 90 项、前端 19 项、E2E 25 项 |
| 部署 | Docker + docker-compose | |

---

## 3. 核心数据契约：Trace

Trace 是**全平台单一数据源**：可视化、练习判分、AI 讲解、历史回放全部消费它。

权威定义见 `docs/contracts/trace.md`，实现见：
- 后端 `backend/app/schemas/trace.py`（定义 snake_case，序列化为 camelCase）
- 前端 `frontend/src/types/trace.ts`

### 3.1 结构

```
Trace
├─ algorithm, keyBits, mode, rounds, input, key, output
├─ keySchedule: KeyScheduleRound[]（长度 rounds+1）
│   └─ round, words[4], detail{rotWord, subWord, rcon, xor} | null
└─ steps: Step[]（长度 40/48/56）
    ├─ index, round, op
    ├─ stateBefore, stateAfter（32 位 hex，列主序）
    ├─ roundKey（仅 AddRoundKey）
    ├─ cells: CellChange[]（恒 16 项）
    │   └─ row, col, before, after, aux
    └─ explain（中文说明，AI 降级时直接使用）
```

### 3.2 关键不变量（由测试强制）

1. `steps[0].stateBefore === input`
2. `steps[-1].stateAfter === output`
3. `steps[i].stateAfter === steps[i+1].stateBefore`
4. `steps[i].index === i`
5. 每个 Step 的 `cells.length === 16`
6. 步数：128→40，192→48，256→56

### 3.3 列主序约定

`flat[4*c + r] === state[r][c]`。这是最容易出错的实现点，因此在前后端各有一处注释与专门测试。

---

## 4. 模块设计

### 4.1 AES 引擎（`backend/app/core/aes/`）

| 文件 | 职责 |
|---|---|
| `sbox.py` | S 盒、逆 S 盒、Rcon 常量表（硬编码，由推导式生成后固化） |
| `gf.py` | GF(2⁸) 的 xtime / gmul / ginv |
| `key_expansion.py` | 密钥扩展，产出各轮字与四步明细 |
| `rounds.py` | 四个轮函数及其逆运算，均为纯函数并产出 cells 明细 |
| `engine.py` | 组装 Trace，加解密入口，含首尾一致性断言 |

**解密实现策略**：先算出对应明文下的加密步骤，再整体逆序并把操作名映射为逆操作、互换 before/after。这样解密动画与加密动画逐帧对应，天然避免逆向顺序写错。

### 4.2 播放控制器（`frontend/src/stores/player.ts`）

有限状态机，状态为 `idle | playing | paused | finished`，游标 `cursor ∈ [0, steps.length-1]`。

设计上刻意分离「当前进度」与「渲染」：组件只读 `currentStep`，所有交互（播放、单步、跳轮、调速、练习冻结）都只改游标。新增交互方式不需改动动画代码。

定时器间隔为 `1200 / speed` 毫秒；`dispose()` 必须由组件卸载时调用，防止幽灵推进。

### 4.3 前端组件

| 组件 | 职责 |
|---|---|
| `StateMatrix.vue` | 4×4 矩阵渲染，逐格高亮、色阶、点击回调 |
| `SBoxPanel.vue` | S 盒 16×16 表格，悬停提示、按值反查 |
| `StepTimeline.vue` | 按轮分组的时间轴，点击定位 |
| `PlayerControls.vue` | 播放控制条 |
| `KeyScheduleView.vue` | 密钥扩展，可折叠，跟随播放轮次自动展开 |
| `AiTutorPanel.vue` | 对话面板，SSE 流式渲染，步骤上下文注入 |
| `ExercisePanel` 逻辑在 `views/Exercise.vue` | 三题型呈现与判分 |

### 4.4 后端接口

| 方法 | 路径 | 说明 | 鉴权 |
|---|---|---|---|
| POST | `/api/auth/register` | 注册 | 否 |
| POST | `/api/auth/login` | 登录，返回 JWT | 否 |
| GET | `/api/auth/me` | 当前用户 | 是 |
| POST | `/api/crypto/aes` | 生成 Trace | 可选 |
| GET | `/api/crypto/sbox` | S 盒 / 逆 S 盒 | 否 |
| GET | `/api/history/sessions` | 历史分页 | 是 |
| GET | `/api/history/sessions/{id}` | 记录详情 + 回放 | 是 |
| DELETE | `/api/history/sessions/{id}` | 删除本人记录 | 是 |
| POST | `/api/exercise/generate` | 出题 | 是 |
| POST | `/api/exercise/submit` | 判分 | 是 |
| POST | `/api/ai/tutor/chat` | AI 对话（SSE） | 是 |
| GET | `/api/ai/conversations/{id}` | 会话历史 | 是 |
| GET | `/api/health` | 健康检查 | 否 |

统一响应：`{code, message, data}`。成功 `code=0`，失败为字符串错误码（如 `E_KEY_LENGTH`）。

错误码：`E_INPUT_FORMAT` `E_KEY_LENGTH` `E_AUTH_FAILED` `E_TOKEN_INVALID` `E_USER_EXISTS` `E_NOT_FOUND` `E_FORBIDDEN` `E_RATE_LIMITED` `E_AI_UNAVAILABLE` `E_INTERNAL`。

### 4.5 数据库设计

| 表 | 关键字段 | 用途 |
|---|---|---|
| `users` | id, username(unique), password_hash, role, created_at | 账号 |
| `crypto_sessions` | id, user_id, algorithm, mode, key_bits, input_hex, key_hex, output_hex, rounds, trace_json, created_at | 加解密记录，trace_json 支持回放 |
| `exercises` | id, type, difficulty, snapshot_json, expected, analysis, step_index, created_at | 题目与标准答案 |
| `exercise_attempts` | id, user_id, exercise_id, answer, is_correct, created_at | 作答记录 |
| `ai_conversations` | id, user_id, session_id, created_at | 会话 |
| `ai_messages` | id, conversation_id, role, content, created_at | 消息，取最近 6 条作为上下文 |

**为什么存 trace_json 而不重算**：保证历史回放与当时所见完全一致；算法实现若后续调整（如新增算法），旧记录仍可正确回放。

**为什么不引入 Alembic**：本期为单次交付，无跨版本迁移需求；建表用 `SQLModel.metadata.create_all` 幂等执行即可。若后续长期维护，应补迁移工具。

### 4.6 AI 辅导设计

**受控注入**，不是自由聊天。每轮请求由后端拼装固定三段式：

```
【角色】密码学助教，零基础讲解，结合具体字节，不超过 200 字，不给完整练习答案
【上下文】算法 / 模式 / 当前第几轮第几步 / 输入输出状态 / 本次变化的字节与依据
【历史】最近 6 条消息
【问题】用户输入（≤500 字）
```

用户只能控制【问题】段，因此无法诱导改写角色或规则。

**上下文管理**：
- 只保留当前步骤摘要 + 最近 6 条消息，控制成本与延迟。
- 用户切换步骤时前端传入新 `stepContext`，后端校验后使用；同时前端清空对话，避免上下文错位。

**降级**：`AI_ENABLED=false`、无密钥、超时（10 s）、HTTP 非 200 时，返回该步骤 `explain` 字段的本地讲解，仍以 SSE 格式输出，前端不区分渲染逻辑。三种场景均有测试覆盖。

**限流**：按用户 20 次/分钟，内存滑动窗口。多实例部署需换 Redis。

### 4.7 练习模式设计

题目由服务端基于**真实 Trace** 生成并落库，判分只读数据库中的 `expected`，绝不信任前端。

| 题型 | 生成方式 | 判分 |
|---|---|---|
| `step_identify` | 随机取一步，四选一（正确 op + 3 个干扰 op） | 字符串等值 |
| `cell_result` | 随机取会改变字节的步骤，指定单元格求值 | 小写化后等值 |
| `key_param` | 随机密钥，问指定轮指定字节 | 小写化后等值 |

答错返回 `analysis`（含推导）与 `stepIndex`，前端据此跳转到对应动画步，形成「练习 → 纠错 → 回看」闭环。

---

## 5. 关键设计决策与理由

### 5.1 用 DOM + CSS Grid 而非 Canvas 渲染状态矩阵

关于渲染方式的权衡：

1. 单元格需要点击事件查看字节来历，DOM 事件比 Canvas 命中检测简单可靠；
2. 每格高亮过渡直接用 CSS `transition`，无需手写动画循环；
3. 16 个单元格的 DOM 数量在此规模下无性能问题（实测切换无延迟）。

Canvas 的价值在大量位移动画，若后续要做「字节飞入飞出」的连续动画，再引入离屏 Canvas 优化。

### 5.2 自研 AES 引擎而非调用加密库

可视化的前提是拿到每一步中间状态。通用库只暴露输入输出，无法提供 S 盒替换前后、列混合中间量。因此轮函数全部自研，用 FIPS-197 标准向量对拍保证正确性。

这既是技术要求，也避免「平台演示了一个错误过程」这种致命问题。

### 5.3 单一数据源 Trace

若播放、判分、AI 各自计算，必然出现状态不一致（经典 bug：动画显示的密文与实际结果不符）。因此加解密只在一处发生，输出统一 Trace，其他模块只消费。

### 5.4 播放控制与渲染分离

见 §4.2。这样播放、单步、跳转、调速、练习冻结共享一套状态机。

### 5.5 不用 passlib，直调 bcrypt

实测 passlib 1.7.4 与 bcrypt 5.0 不兼容：它为读取版本号访问已移除的 `bcrypt.__about__.__version__`，抛 `ValueError`；且其对超长口令的处理与 bcrypt 5 冲突。

改为直接调用 bcrypt，并显式拒绝超过 72 字节的口令（而非静默截断，截断会造成「密码前 72 字节相同即可登录」的安全隐患）。

### 5.6 认证用 Bearer 头而非 Cookie

令牌放 `Authorization` 头，不使用 Cookie，因此**天然免疫 CSRF**（跨站请求无法自动携带该头）。同时保留 Origin 校验作为纵深防御。

### 5.7 越权返回 404 而非 403

若他人记录返回 403，攻击者可据此枚举「哪些 id 存在」。统一返回 404 不泄露资源存在性。

---

## 6. 安全设计

| 风险 | 措施 | 实现位置 |
|---|---|---|
| XSS | 前端不使用 `v-html` 渲染用户/AI 内容；CSP 限制 script-src 为 self；用户名正则禁止尖括号 | `security_headers.py`、`StateMatrix`/`AiTutorPanel` 文本插值 |
| CSRF | 令牌走 Authorization 头，不用 Cookie | `deps.py` |
| 输入校验 | Pydantic 的 pattern 约束 hex 长度与字符集；stepContext 逐字段校验 | `schemas/trace.py`、`services/ai/prompt.py` |
| 口令安全 | bcrypt cost=12，拒绝超 72 字节，不记录明文 | `core/security.py` |
| 越权 | 所有历史与对话查询按 user_id 过滤，不匹配返回 404 | `routers/history.py`、`routers/ai.py` |
| 滥用 | AI 接口按用户限流 20 次/分 | `middleware/rate_limit.py` |
| 信息泄露 | 安全响应头、生产环境隐藏详细错误、不返回口令字段 | `main.py` |
| 合规 | 仅采集用户名与口令散列，不采集手机号等敏感信息；提供记录删除 | 全局 |

**安全要点**：
- 《网络安全法》：采取技术措施保障网络安全，本项目落实输入校验与访问控制。
- 《数据安全法》：数据分类分级与最小必要，本项目仅存学习记录。
- 《个人信息保护法》：最小必要原则、用户可删除本人数据（`DELETE /api/history/sessions/{id}`）。

---

## 7. 部署架构

```
用户浏览器
   │  HTTPS
   ▼
Nginx（静态资源 + /api 反向代理）
   ├── frontend/dist（Vue 构建产物）
   └── /api → uvicorn:8000（FastAPI）
                  │
                  └── MySQL 8 / SQLite 文件
```

开发期用 Vite 的 `/api` 代理避免跨域；生产由 Nginx 同源反代。详细步骤见 `deploy.md`。

---

## 8. 已知限制与后续改进

| 限制 | 影响 | 改进方向 |
|---|---|---|
| 限流器为内存实现 | 多实例部署时限流不共享 | 换 Redis |
| 无数据库迁移工具 | 表结构变更需手工处理 | 引入 Alembic |
| 一次只处理单个 16 字节分组 | 不支持长文本加密 | 增加分组模式（CBC/GCM）与填充 |
| AI 无内容安全审核 | 依赖模型自身约束 | 接入审核接口 |
| 未做移动端适配 | 小屏体验一般 | 增加响应式断点 |
| 时间轴横向滚动 | 轮次多时需左右拖动 | 改为可缩放的总览条 |