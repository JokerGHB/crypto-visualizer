# 密码学算法可视化教学与 AI 辅导平台

AES 加解密的每一步都看得见，并且能停下来问 AI「这里为什么这样变」。

课程：企业项目训练 II · 方向一 · 网络工程 231/232/233
开发平台：华为云 CodeArts

---

## 项目简介

AES 的运算全部发生在一次函数调用之内，学生看得到明文和密文，看不到中间过程。本项目把 4×4 状态矩阵、S 盒替换、行移位、列混合、轮密钥加逐步拆开展示，并提供一个能结合当前停留步骤讲解的 AI 辅导面板。

**核心设计**：后端是唯一的数据来源。所有可视化、练习判分、AI 讲解、历史回放都消费同一份 `Trace` 数据，前端不做任何算法计算。因此「动画显示的」和「实际算出来的」永远一致。

### 主要功能

| 功能 | 说明 |
|---|---|
| 全流程可视化 | AES-128/192/256 加解密，40/48/56 步完整轨迹 |
| 逐步播放 | 播放、暂停、单步、跳轮、调速、重置；方向键与空格快捷键 |
| 逐字节追溯 | 点击任意单元格查看该字节的变化前后与计算依据 |
| S 盒查询 | 标准/逆 S 盒 16×16 表格，悬停提示、按值反查 |
| 密钥扩展 | W 数组生成，RotWord / SubWord / Rcon / XOR 四步明细 |
| AI 辅导 | 结合当前步骤的流式对话；服务不可用时降级为本地讲解 |
| 历史记录 | 自动保存、分页、回放、删除 |
| 练习模式 | 三种题型服务端判分，答错可跳回对应动画步 |
| 安全防护 | 输入校验、CSP、JWT、限流、越权返回 404 |

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 20+，pnpm 9+
- 可选：MySQL 8（生产）、Docker 24+

### 1. 后端

> **虚拟环境位置固定为 `backend/.venv`**，不要在项目根目录另建 `.venv`。
> 两份并存会导致「一处装了包、另一处报 ModuleNotFoundError」。

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt

# 从模板创建配置
cp ../.env.example ../.env

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Windows 上如果 `python` 命令无效**（跳转到应用商店），有两种绕法：

```powershell
# 绕法 A：直接用 venv 内解释器，不依赖 PATH
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 绕法 B：用 py 启动器
py -m venv .venv
```

根治办法见 [部署文档 · 常见问题](docs/deploy.md)：关闭「应用执行别名」中的 `python.exe`。

接口文档：<http://127.0.0.1:8000/docs>

### 2. 前端

```bash
cd frontend
pnpm install
pnpm dev
```

访问 <http://localhost:5200>。开发期 Vite 已把 `/api` 代理到后端，无需处理跨域。

### 3. Docker 一键启动

```bash
docker compose up -d --build
# 访问 http://localhost
```

---

## 项目结构

```
crypto-visualizer/
├── backend/
│   ├── app/
│   │   ├── core/aes/          # AES 引擎：sbox / gf / key_expansion / rounds / engine
│   │   ├── core/              # 安全、错误码
│   │   ├── middleware/        # 安全响应头、限流
│   │   ├── models/            # SQLModel 表定义
│   │   ├── routers/           # auth / crypto / history / exercise / ai
│   │   ├── schemas/           # Trace 契约、统一响应包装
│   │   ├── services/          # 练习生成判分、AI 适配与提示词
│   │   └── main.py
│   ├── tests/                 # 95 项测试
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/               # 接口封装，含 SSE 流式解析
│   │   ├── components/        # StateMatrix / SBoxPanel / PlayerControls / ...
│   │   ├── stores/            # player（播放状态机）、auth
│   │   ├── views/             # Home / Playground / SBox / Exercise / History / Login
│   │   └── types/trace.ts     # Trace 的 TypeScript 镜像
│   ├── e2e/verify.mjs         # Playwright 端到端验证（25 项）
│   ├── Dockerfile
│   └── nginx.conf
├── docs/
│   ├── requirement.md         # 需求分析
│   ├── design.md              # 系统设计
│   ├── deploy.md              # 部署文档
│   ├── test-report.md         # 测试报告
│   ├── contracts/trace.md     # Trace 数据契约（冻结）
│   └── status.md              # 完成情况清单
├── verify/                    # 独立参考实现，用于对拍
├── docker-compose.yml
└── .codearts/pipeline.yml     # CodeArts 流水线
```

---

## 测试

```bash
# 后端：95 项
cd backend && pytest -q

# 前端：19 项
cd frontend && pnpm test

# 端到端：25 项（需先启动前后端）
cd frontend && node e2e/verify.mjs
```

测试覆盖重点：

- **算法正确性**：FIPS-197 四条标准向量、S 盒推导、GF(2⁸) 运算、列混合手算、密钥扩展
- **契约一致性**：步数、状态首尾相接、每步 16 个 cell、列主序
- **接口行为**：鉴权、越权 404、非法输入 422、限流 429
- **降级路径**：AI 关闭 / 无密钥 / 超时三种场景
- **前端状态机**：游标边界、定时器清理、冻结、进度计算
- **真实浏览器**：加密解密结果、参数切换、S 盒反查、登录存历史、练习判分、AI 流式

---

## 关键实现说明

### 为什么自研 AES 而不调用加密库

可视化需要每一步的中间状态，通用库只暴露输入输出。轮函数全部自研，并用 FIPS-197 标准向量对拍保证正确性。

### 为什么用 DOM + CSS Grid 而非 Canvas

单元格需要点击溯源，DOM 事件比 Canvas 命中检测简单可靠；16 格规模下无性能问题。若后续要做字节飞入飞出的连续动画，再引入 Canvas。

### 为什么不用 passlib

passlib 1.7.4 与 bcrypt 5.x 不兼容（读取已移除的 `bcrypt.__about__.__version__`）。改为直接调用 bcrypt，并显式拒绝超过 72 字节的口令 —— 而非静默截断，因为截断会造成「前 72 字节相同即可登录」的安全隐患。

### 为什么令牌走 Authorization 头而非 Cookie

跨站请求无法自动携带自定义头，因此天然免疫 CSRF，同时保留 Origin 校验作纵深防御。

---

## 配置

复制 `.env.example` 为 `.env` 后按需修改，关键项：

| 变量 | 说明 |
|---|---|
| `JWT_SECRET` | **生产必须替换**为随机长字符串 |
| `DATABASE_URL` | 开发用 SQLite，生产改 MySQL 连接串 |
| `CORS_ORIGINS` | 允许的前端来源，逗号分隔 |
| `AI_ENABLED` / `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL` | AI 服务；留空则自动降级 |
| `AI_RATE_LIMIT_PER_MINUTE` | 每用户每分钟请求数，默认 20 |

完整说明见 [部署文档](docs/deploy.md)。

---

## 文档

- [需求分析](docs/requirement.md)
- [系统设计](docs/design.md)
- [部署文档](docs/deploy.md)
- [测试报告](docs/test-report.md)
- [Trace 数据契约](docs/contracts/trace.md)
- [完成情况清单](docs/status.md)

---

## 已知限制

1. 限流器为进程内存实现，多实例部署需换 Redis。
2. 一次性处理单个 16 字节分组，不支持长文本（未做 CBC/GCM 与填充）。
3. 未引入 Alembic，表结构变更需手工处理。
4. AI 输出无内容安全审核，依赖模型自身约束。
5. 移动端适配未做，小屏体验一般。

---

## 许可

本项目为课程作业，仅用于教学演示。