# 部署文档

## 1. 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.12+ | 后端运行时 |
| Node.js | 20+ | 前端构建 |
| pnpm | 9+ | 包管理器（也可用 npm） |
| MySQL | 8.0+ | 生产数据库，开发可用 SQLite |
| Docker | 24+ | 可选，容器化部署 |

---

## 2. 本地开发部署

### 2.1 后端

```bash
cd backend

# 创建虚拟环境（位置固定为 backend/.venv，不要在项目根目录另建）
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

> **为什么要强调位置**：曾出现项目根目录与 `backend/` 下各有一个 `.venv` 的情况，
> 结果一边装了依赖、另一边启动时报 `ModuleNotFoundError: No module named 'fastapi'`。
> 只保留 `backend/.venv` 一份，团队协作时才不会互相踩坑。

**Windows 上 `python` 命令无效**（输出 "Python was not found; run without arguments to install from the Microsoft Store"）时：

```powershell
# 方案 A：直接用 venv 内解释器，完全绕开 PATH 问题（推荐，一定能用）
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 方案 B：用 py 启动器（Windows 独有）
py -m venv .venv
```

根治办法见本文末尾「常见问题 · python 命令跳转到应用商店」。

复制配置文件：

```bash
cp .env.example ../.env
```

编辑 `.env`，至少确认 `JWT_SECRET`：

```ini
DEBUG=true
DATABASE_URL=sqlite:///./crypto_visualizer.db
JWT_SECRET=<请替换为随机长字符串>
AI_ENABLED=true
AI_BASE_URL=https://your-provider/v1
AI_API_KEY=<你的密钥>
AI_MODEL=<模型名>
```

启动：

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

验证：访问 <http://127.0.0.1:8000/docs> 能看到接口文档，或：

```bash
curl http://127.0.0.1:8000/api/health
# {"code":0,"message":"ok","data":{"status":"healthy"}}
```

### 2.2 前端

```bash
cd frontend
pnpm install
pnpm dev
```

访问 <http://localhost:5173>。开发期 Vite 已配置 `/api` 代理到 `127.0.0.1:8000`，无需额外跨域设置。

---

## 3. 生产部署

### 3.1 数据库准备（MySQL）

```sql
CREATE DATABASE crypto_visualizer
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'crypto'@'%' IDENTIFIED BY '<强口令>';
GRANT ALL PRIVILEGES ON crypto_visualizer.* TO 'crypto'@'%';
FLUSH PRIVILEGES;
```

安装驱动并配置连接串：

```bash
pip install pymysql
```

```ini
DATABASE_URL=mysql+pymysql://crypto:<强口令>@127.0.0.1:3306/crypto_visualizer?charset=utf8mb4
```

表在应用启动时自动创建（`init_db()`），幂等可重复执行。

### 3.2 前端构建

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm build
# 产物在 frontend/dist
```

如前后端分离部署（不同域名），构建时指定后端地址：

```bash
VITE_API_BASE_URL=https://api.example.com pnpm build
```

同源部署（推荐）则留空，由 Nginx 反代 `/api`。

### 3.3 后端运行

```bash
cd backend
pip install -r requirements.txt gunicorn pymysql
```

```bash
gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 4 \
  -b 127.0.0.1:8000 \
  --access-logfile - \
  --error-logfile -
```

### 3.4 Nginx 配置

```nginx
server {
    listen 80;
    server_name crypto.example.com;

    # 前端静态资源
    root /var/www/crypto-visualizer/dist;
    index index.html;

    # SPA 路由回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端反代
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 必需：关闭缓冲，否则 AI 流式输出会整段延迟
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # 静态资源缓存
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

> **SSE 注意**：`proxy_buffering off` 是 AI 流式对话正常工作的前提。缺少这项会出现「回答突然整段出现」而非逐字输出。

### 3.5 HTTPS

```bash
certbot --nginx -d crypto.example.com
```

---

## 4. Docker 部署

```bash
# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

服务端口：前端 80，后端 8000（仅容器网络内可用）。

自定义配置通过 `.env` 文件注入，`docker-compose.yml` 已引用。

---

## 5. 配置项说明

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEBUG` | `true` | 生产设 `false` |
| `DATABASE_URL` | SQLite 文件 | 生产改 MySQL |
| `JWT_SECRET` | 开发占位值 | **生产必须替换**，泄露可伪造任意用户 |
| `JWT_EXPIRE_MINUTES` | 1440 | 令牌有效期（分钟） |
| `CORS_ORIGINS` | 本地 5173 | 生产改为实际域名 |
| `AI_ENABLED` | `true` | 设 `false` 可强制降级 |
| `AI_BASE_URL` | 空 | OpenAI 兼容接口地址 |
| `AI_API_KEY` | 空 | 留空则自动降级为本地讲解 |
| `AI_MODEL` | 空 | 模型标识 |
| `AI_TIMEOUT` | `90` | 单次请求超时（秒） |
| `AI_RATE_LIMIT_PER_MINUTE` | `20` | 每用户每分钟次数 |

### AI 密钥配置

优先级：**真实环境变量 > `.env` 文件 > 代码默认值**。

**推荐做法：环境变量设一次，`.env` 写占位符**

密钥只需设置一次，之后每次启动都不用手输：

```powershell
# ① 一次性设置（写入用户环境变量，永久有效）
[Environment]::SetEnvironmentVariable('GPT_API_KEY', 'sk-你的密钥', 'User')

# ② 之后每次启动，直接跑即可
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

`.env` 里对应写占位符，由 python-dotenv 自动展开：

```ini
AI_API_KEY=${GPT_API_KEY}
```

变量缺失时该行解析为空串，AI 自动降级为本地讲解——不会报错，也不会把字面量 `${GPT_API_KEY}` 当密钥。

> **注意**：设置环境变量后，**已经打开的终端读不到**。因为进程环境是启动时的快照，不是实时查询注册表。所以设置完需要重开一次终端（或重启 IDE）。之后新开的终端都会自动继承，不必再设第二次。

**不推荐的两种写法**

```ini
# ✗ 直接把密钥写进 .env：能跑，但密钥在磁盘明文存在
AI_API_KEY=sk-你的密钥
```

```powershell
# ✗ 每次启动前手动 export：确实要每次输，很麻烦
$env:GPT_API_KEY = 'sk-你的密钥'
```

第二种只在临时调试（不想污染全局变量）时才用。

**另一种等价思路：不在 `.env` 写占位符**

因为本项目直接读取环境变量名，所以 `.env` 里 `AI_API_KEY` 留空、只靠 `GPT_API_KEY` 也能工作：

```ini
AI_API_KEY=
```

代码会按 `GPT_API_KEY` → `AI_API_KEY` → `OPENAI_API_KEY` 顺序查找。写占位符的好处是**看 `.env` 就能知道密钥来自哪个变量**，意图更明确。

**容器部署**

```yaml
# docker-compose.yml
environment:
  GPT_API_KEY: ${GPT_API_KEY:-}
```

密钥从宿主机环境传入容器，compose 文件里不含密钥。启动前确保宿主机已设置该变量。

**关于 `${VAR:默认值}` 语法**

bash 的 `${VAR:-default}` 写法**不被支持**，会被当字面量原样保留。python-dotenv 只支持 `${VAR}` 和 `$VAR` 两种形式。需要默认值时请写在代码的字段默认值里，而不是 `.env` 中。

### 启动自检

后端启动时打印脱敏摘要，密钥只显示末 4 位：

```
配置自检:
  DEBUG            = True
  DATABASE_URL     = sqlite:///./crypto_visualizer.db
  JWT_SECRET       = 使用开发默认值（生产必须替换）
  AI_BASE_URL      = https://your-provider/v1
  AI_MODEL         = your-model
  AI_API_KEY       = ***Z7QW
  密钥来源         = GPT_API_KEY
  AI 状态          = 已就绪
```

若显示「未就绪，将降级为本地讲解」，会同时列出缺失项与修复提示，不必再猜「为什么 AI 一直离线」。

### AI 超时为什么要设 90 秒

实测某兼容端点首字节延迟在 10~45 秒之间波动。原默认值 10 秒会导致**稳定超时降级**——用户看到「AI 服务不可用」，但实际链路是通的，只是慢。

流式输出下首字节到达后文字逐字出现，放宽超时不会让人觉得卡住。若服务商响应很快，可调回 15~30 秒。

生产环境检查清单：

- [ ] `JWT_SECRET` 已替换为随机长字符串（建议 `openssl rand -hex 32`）
- [ ] `DEBUG=false`
- [ ] `DATABASE_URL` 指向 MySQL 且使用强口令
- [ ] `CORS_ORIGINS` 只包含实际域名
- [ ] `.env` 未提交到仓库（已在 `.gitignore`）
- [ ] 已配置 HTTPS
- [ ] Nginx 已关闭 `/api` 的 `proxy_buffering`（SSE 需要）
- [ ] 已设置数据库定期备份

---

## 6. 运维

### 6.1 健康检查

```bash
curl -f http://127.0.0.1:8000/api/health || echo "服务异常"
```

### 6.2 日志

```bash
# Docker
docker compose logs -f backend

# systemd
journalctl -u crypto-visualizer -f
```

### 6.3 数据库备份

```bash
# MySQL
mysqldump -u crypto -p crypto_visualizer > backup_$(date +%Y%m%d).sql

# SQLite
cp crypto_visualizer.db backup_$(date +%Y%m%d).db
```

### 6.4 回滚

代码回滚：

```bash
git checkout <上一个稳定 tag>
docker compose up -d --build
```

数据库回滚：表结构无迁移记录，如需回滚需导入备份。这也是本期未引入 Alembic 的代价，长期维护应补上。

---

## 7. 常见问题

**Q：前端页面能打开但接口 404**

Nginx 未配置 `/api` 反代，或前后端分离时未设置 `VITE_API_BASE_URL`。

**Q：AI 回答整段突然出现，不是逐字输出**

Nginx 缺少 `proxy_buffering off`，或中间有 CDN 缓存了 SSE。

**Q：登录后刷新页面就退出**

`JWT_SECRET` 每次重启变化（未固定配置），导致旧令牌无法验签。固定 `JWT_SECRET` 即可。

**Q：口令注册报「口令不得超过 72 字节」**

bcrypt 的硬限制。项目选择显式拒绝而非静默截断，因为截断会造成前 72 字节相同即可登录的安全隐患。

**Q：`passlib` 相关报错**

本项目不使用 passlib，直接调用 bcrypt。若看到 passlib 报错，说明安装了额外依赖或使用了旧版本代码，请检查 `requirements.txt`。

**Q：AI 接口返回 429**

触发限流（默认 20 次/分）。等待一分钟或调整 `AI_RATE_LIMIT_PER_MINUTE`。

**Q：`ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION`**

pnpm 10.x 内置的供应链保护：默认拒绝安装发布不足一定时长（默认 1440 分钟）的包。本项目用到刚发布的 Vue 3.5.45，会被拦截：

```
× installing dependencies
╰─▶ 15 lockfile entries failed verification:
      @vue/compiler-core@3.5.45 was published at ...,
      within the minimumReleaseAge cutoff ...
```

项目已在 **`frontend/pnpm-workspace.yaml`** 中关闭：

```yaml
minimumReleaseAge: 0
verifyDepsBeforeRun: false
```

> **注意位置**：这两个键必须写在 `pnpm-workspace.yaml`，**不能写在 `.npmrc`**。
> pnpm 10.16 起把依赖校验与供应链策略类设置迁到了 workspace 文件。
> 写在 `.npmrc` 时 `pnpm config get` 能读到值，但 `pnpm run` 前触发的隐式
> install 不会应用它，表现为「配置看着生效了、`pnpm dev` 仍然报错」。

**`verifyDepsBeforeRun: false` 的作用**：不关闭时，`pnpm dev` 会先跑一次
依赖校验 install，该校验若失败，脚本根本执行不到 `vite`，报错为
`'vite' 不是内部或外部命令` —— 这个报错具有误导性，真实原因是上游 install 失败。

**这个保护是干什么的**：防御「投毒包秒发秒装」攻击 —— 攻击者抢注合法包名后立即发布，受害者若在几小时内安装就会中招。本项目关闭它，是因为依赖版本由 `pnpm-lock.yaml` 锁定且已人工核对。**生产项目建议保留**，或缩短到 60 分钟：

```yaml
minimumReleaseAge: 60
```

**Q：`'vite' 不是内部或外部命令`**

两种可能：

1. `node_modules` 顶层符号链接缺失（结构损坏）→ 执行 `pnpm install` 重建
2. `verifyDepsBeforeRun` 校验失败导致 install 中断 → 见上一条

检查是否损坏：

```powershell
Test-Path node_modules\vite            # 应为 True
Test-Path node_modules\.bin\vite       # 应为 True
Test-Path node_modules\.modules.yaml   # 应为 True
```

**Q：`python` 命令跳到 Microsoft Store**

Windows 的**应用执行别名**在干扰。`%LOCALAPPDATA%\Microsoft\WindowsApps\` 里预置了 0 字节的 `python.exe`、`python3.exe` 重解析点，指向商店的 Python，而你装的是 python.org 版本，跳转目标不存在，于是报找不到。

注意两个独立原因，容易混淆：

1. **PATH 里 `WindowsApps` 排在 Python 安装目录之前** → 系统优先命中占位符
2. **已打开的终端不会自动刷新 PATH** → 装完必须开新终端

根治（推荐）：

设置 → 应用 → 高级应用设置 → **应用执行别名** → 关闭 `python.exe` 与 `python3.exe`

验证：

```powershell
# 需开新终端
python --version
# 期望输出 Python 3.12.x
```

临时绕法（不改系统设置）：

```powershell
py --version                                                    # Windows 启动器
.venv\Scripts\python.exe --version                              # venv 内解释器
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -V   # 完整路径
```

等价的命令行做法（把占位符改名而非删除，便于恢复）：

```powershell
Rename-Item "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"  "python.exe.disabled"
Rename-Item "$env:LOCALAPPDATA\Microsoft\WindowsApps\python3.exe" "python3.exe.disabled"
```

**Q：启动报 `ModuleNotFoundError: No module named 'fastapi'`**

用错了解释器。确认 `python -c "import sys; print(sys.executable)"` 输出的是 `backend\.venv\Scripts\python.exe`。若显示系统 Python 或项目根目录的 `.venv`，说明虚拟环境不唯一 —— 删掉多余的，只保留 `backend/.venv`。