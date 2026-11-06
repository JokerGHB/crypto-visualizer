# 密码学算法可视化教学与 AI 辅导平台 — 实施规格书

> 本文件是**给执行本项目的 AI 编码代理**看的作业指令书，不是给人阅读的宣传材料。
> 每一条都是可直接执行或可直接判定的要求。遇到歧义时按 `## 11 决策优先级` 处理，不要自行扩大范围。

**目标产物**：一个可运行、可演示、已部署的 Web 平台，实现 AES 加解密全流程逐步可视化 + 步骤级 AI 辅导 + 练习模式 + 用户与历史记录。
**硬约束**：技术栈、目录结构、数据契约、验收命令均不得擅自更改（见第 3、4、5、6 节）。

---

## 0. 执行须知（Read First）

1. **单一数据源原则**：所有可视化、练习判分、AI 讲解、历史回放，**只允许**消费 `Trace` 对象（见第 5 节）。禁止任何模块自行重算算法中间态。
2. **不引入现成加密库做演示**：不得用 `crypto-js` / `pycryptodome` / `node:crypto` 生成可视化用的中间状态。算法轮函数必须自己实现。允许在**单元测试**中调用标准库做对拍验证。
3. **契约先冻结**：`Trace` 的字段定稿后，新增字段只允许向后兼容（可选字段），不得重命名、不得改类型。改契约必须同步改 `docs/contracts/trace.md` 与前后端两处类型定义，并在 PR 描述中标注 `BREAKING`。
4. **不写占位实现**：不允许出现 `TODO`、`pass`、`return None` 假数据、写死的假 Trace。每个功能点必须真实可用且已联调。
5. **AI 依赖可失败**：任何调用外部大模型的代码路径，必须有无网络/无密钥时的降级分支（第 8.4 节）。降级分支必须被测试覆盖。
6. **每完成一个功能点就更新** `docs/status.md` 的勾选状态，不要等最后补。

---

## 1. 任务来源与不可删项

来源于《企业项目训练 II 实习任务书（密码方向）》。以下为**验收判定项，缺一即不合格**，不得删减或降级：

| 编号 | 要求 | 判定方式 |
|---|---|---|
| R1 | AES 加解密流程可视化：字节替代、行移位、列混合、轮密钥加 | 四步均有动画，可逐步查看 |
| R2 | S 盒 / 逆 S 盒、状态矩阵（4×4 字节）动态展示 | 两个表格可查，矩阵有高亮动画 |
| R3 | 轮密钥生成与密钥扩展可视化 | 展示 W 数组生成、RotWord/SubWord/Rcon |
| R4 | 逐步播放、单步执行、参数调节 | 播放/暂停/前进/后退/跳轮/调速/改参数均可用 |
| R5 | AI 智能体：步骤级讲解 + 辅导对话 | 停在哪步就问哪步，支持多轮追问 |
| R6 | 后端接口与数据库：FastAPI + RESTful + SQLite/MySQL | 接口可在 `/docs` 调试，数据落库 |
| R7 | 用户管理 + 算法历史记录 | 注册登录、历史回放、删除 |
| R8 | 交互式练习模块 | 至少 3 类题型，服务端判分 |
| R9 | 输入校验、XSS 防护、CSRF 防护 | 每项有实现位置与测试用例 |
| R10 | 单元测试 + 功能测试 | `pytest` 通过，用例表齐备 |
| R11 | 部署上线 | 提供可访问 URL |
| R12 | 需求文档、设计文档、部署文档 | 三份文件存在于 `docs/` |
| R13 | CodeArts + Git 分支 + 代码评审 + CI/CD | 仓库有分支、MR、流水线记录 |

**范围外（不要做）**：生产级加密工具、密钥托管服务、移动端 App、多语言 i18n、对接真实教务系统、用户上传文件解密等。

---

## 2. 术语与命名约定

| 术语 | 定义 |
|---|---|
| state | AES 状态矩阵，4×4 字节，**列主序**：`state[r][c]` 对应字节序号 `4*c+r` |
| word | 密钥扩展中的 4 字节字，`W[i]` |
| round | 轮次，AES-128 为 10，192 为 12，256 为 14；轮次编号从 0（初始轮密钥加）到 Nr（最终轮） |
| step | Trace 中的一步，是可视化的最小单位 |
| Trace | 一次加/解密产生的完整步骤序列对象，见第 5 节 |
| cursor | 播放游标，`0 <= cursor < steps.length` |

命名硬规则：

- 前端组件 `PascalCase.vue`，组合式函数 `useXxx.ts`，工具函数 `camelCase.ts`。
- 后端模块 `snake_case.py`，Pydantic 模型 `PascalCase`，数据表 `snake_case` 复数。
- 十六进制字符串**统一小写、无 `0x` 前缀、无空格**；长度校验：明文/密文 32 字符，AES-128 密钥 32 字符、192 为 48、256 为 64。
- 所有面向用户的文案用中文；代码注释用中文；变量名用英文。

---

## 3. 技术栈（锁定，勿替换）

| 层 | 选型 | 备注 |
|---|---|---|
| 前端框架 | Vue 3 + Vite + TypeScript | 任务书指定 Vue.js |
| 状态管理 | Pinia | 存播放游标、参数、用户态 |
| 可视化 | Canvas 2D（状态矩阵、动画）+ SVG（S 盒表格、流程箭头） | 任务书指定 |
| UI | Element Plus | 仅用表单/表格/弹窗/消息，视觉自定义 |
| 后端 | FastAPI + Uvicorn + Pydantic v2 | 任务书指定 |
| ORM | SQLModel | 模型即校验模型 |
| 数据库 | SQLite（开发）/ MySQL 8（生产），通过 `DATABASE_URL` 切换 | 任务书指定 |
| 认证 | JWT（`python-jose`）+ bcrypt（`passlib[bcrypt]`） | 不用 Cookie 会话 |
| AI | OpenAI 兼容协议 HTTP 客户端，Provider 适配层 | 厂商可换，见 8.1 |
| 测试 | pytest + httpx（后端）/ Vitest（前端） | |
| 部署 | Docker + docker-compose，镜像推送 CodeArts 制品库 | |

禁止新增的依赖：任何前端图表库（ECharts 等）、任何加密库、任何 UI 框架替代品。新增依赖须在 PR 说明理由。

---

## 4. 仓库结构（必须按此创建）

```
crypto-visualizer/
├─ README.md
├─ docker-compose.yml
├─ .env.example
├─ .gitignore
├─ docs/
│  ├─ requirement.md          # 需求文档
│  ├─ design.md               # 设计文档
│  ├─ deploy.md               # 部署文档
│  ├─ test-report.md          # 测试用例 + 执行结果
│  ├─ contracts/trace.md      # Trace 契约（唯一权威定义）
│  └─ status.md               # 功能点完成状态（逐项勾选）
├─ backend/
│  ├─ pyproject.toml
│  ├─ app/
│  │  ├─ main.py              # FastAPI 实例、中间件、路由挂载
│  │  ├─ config.py            # 环境变量读取（pydantic-settings）
│  │  ├─ deps.py              # 依赖注入：db session、current_user
│  │  ├─ core/
│  │  │  ├─ aes/
│  │  │  │  ├─ sbox.py        # S 盒 / 逆 S 盒 / Rcon 常量表
│  │  │  │  ├─ gf.py          # GF(2^8) 乘法、xtime
│  │  │  │  ├─ key_expansion.py
│  │  │  │  ├─ rounds.py      # sub_bytes/shift_rows/mix_columns/add_round_key
│  │  │  │  └─ engine.py      # 组装 Trace，加解密入口
│  │  │  ├─ security.py       # 口令散列、JWT 编解码
│  │  │  └─ errors.py         # 业务异常与错误码
│  │  ├─ models/              # SQLModel 表定义
│  │  ├─ schemas/             # 请求/响应 Pydantic 模型
│  │  ├─ routers/             # auth / crypto / history / exercise / ai
│  │  ├─ services/            # 业务逻辑（history、exercise、ai）
│  │  └─ middleware/          # 安全响应头、限流
│  └─ tests/
│     ├─ test_aes_vectors.py  # FIPS-197 对拍
│     ├─ test_api.py
│     └─ test_ai_fallback.py
├─ frontend/
│  ├─ package.json
│  ├─ vite.config.ts
│  └─ src/
│     ├─ main.ts
│     ├─ App.vue
│     ├─ router/index.ts
│     ├─ stores/{player.ts,auth.ts,crypto.ts}
│     ├─ api/{client.ts,auth.ts,crypto.ts,history.ts,exercise.ts,ai.ts}
│     ├─ types/trace.ts       # 与 docs/contracts/trace.md 一一对应
│     ├─ views/{Home.vue,Playground.vue,SBox.vue,Exercise.vue,History.vue,Login.vue}
│     ├─ components/
│     │  ├─ StateMatrix.vue
│     │  ├─ SBoxPanel.vue
│     │  ├─ StepTimeline.vue
│     │  ├─ PlayerControls.vue
│     │  ├─ KeyScheduleView.vue
│     │  ├─ AiTutorPanel.vue
│     │  └─ ExercisePanel.vue
│     └─ composables/{usePlayer.ts,useCanvasMatrix.ts,useAiChat.ts}
└─ .codearts/pipeline.yml     # CI/CD 流水线定义
```

---

## 5. Trace 数据契约（核心，先实现这个）

> 权威定义写进 `docs/contracts/trace.md`，前后端各维护一份镜像类型。字段名严格照抄。

### 5.1 TypeScript 类型（前端 `src/types/trace.ts`）

```ts
export type AesKeyBits = 128 | 192 | 256;
export type AesMode = 'encrypt' | 'decrypt';
export type AesOp =
  | 'AddRoundKey' | 'SubBytes' | 'ShiftRows' | 'MixColumns'
  | 'InvSubBytes' | 'InvShiftRows' | 'InvMixColumns';

export interface CellChange {
  row: number;        // 0..3
  col: number;        // 0..3
  before: string;     // 2 位小写 hex
  after: string;      // 2 位小写 hex
  aux?: string;       // 辅助信息：轮密钥字节 / sbox 坐标 "sbox[1][9]" / 乘积 "xtime(0x57)=0xae"
}

export interface Step {
  index: number;          // 从 0 开始，等于数组下标
  round: number;          // 0..Nr
  op: AesOp;
  stateBefore: string;    // 32 位小写 hex，列主序展平
  stateAfter: string;     // 32 位小写 hex
  roundKey?: string;      // 仅 AddRoundKey 步存在，32 位 hex
  cells: CellChange[];    // 逐格明细，至少包含发生变化的格
  explain: string;        // 一句话中文说明，用于无 AI 时的本地讲解
}

export interface KeyScheduleRound {
  round: number;
  words: string[];        // 4 个 8 位 hex
  detail?: {              // 从第 1 轮轮密钥起存在
    rotWord: string;      // 8 位 hex
    subWord: string;
    rcon: string;
    xor: string;
  };
}

export interface Trace {
  algorithm: 'AES';
  keyBits: AesKeyBits;
  mode: AesMode;
  rounds: number;         // 10 | 12 | 14
  input: string;          // 明文（加密）或密文（解密），32 位 hex
  key: string;            // 32/48/64 位 hex
  output: string;         // 结果，32 位 hex
  keySchedule: KeyScheduleRound[];
  steps: Step[];
}
```

### 5.2 Pydantic 镜像（后端 `app/schemas/trace.py`）

字段名、类型、顺序与上表完全一致。`cells` 用 `list[CellChange]`，`explain` 用 `str`。

### 5.3 步骤生成规则（`engine.py` 必须照此产出）

**加密**（以 Nr 表示轮数）：

1. `step(round=0, op='AddRoundKey', roundKey=W[0..3])` — 初始轮密钥加。
2. 对 `r = 1 .. Nr-1`：
   - `SubBytes`（round=r）
   - `ShiftRows`（round=r）
   - `MixColumns`（round=r）
   - `AddRoundKey`（round=r，roundKey=W[4r..4r+3]）
3. 最终轮 `r = Nr`：`SubBytes` → `ShiftRows` → `AddRoundKey`（**无 MixColumns**）。

**解密**：**严格取加密 steps 的逆序**，每个 step 的操作名做如下映射，`round` 与 `stateBefore/stateAfter` 互换：

| 加密 op | 解密 op |
|---|---|
| `AddRoundKey` | `AddRoundKey`（不变） |
| `SubBytes` | `InvSubBytes` |
| `ShiftRows` | `InvShiftRows` |
| `MixColumns` | `InvMixColumns` |

即解密序列形如：`AddRoundKey(Nr)` → `InvShiftRows(Nr)` → `InvSubBytes(Nr)` → `AddRoundKey(Nr-1)` → `InvMixColumns(Nr-1)` → … → `AddRoundKey(0)`。
`keySchedule` 与加密完全相同（不另算），`roundKey` 仍取对应轮次的值。这样实现可保证「解密动画」与「加密动画」逐帧对应，也天然避免逆向顺序写错。

**总步数**：AES-128 加密 = 1 + 9×4 + 3 = 40 步（index 0..39）。192 = 48 步，256 = 56 步。解密步数相同。
**首尾校验**：`steps[0].stateBefore` 必须等于 `input`；`steps[-1].stateAfter` 必须等于 `output`。这两条必须写成断言并纳入测试。

### 5.4 校验（后端入参层必须做）

| 字段 | 规则 | 违反时 |
|---|---|---|
| `input` | 匹配 `^[0-9a-f]{32}$` | `400 E_INPUT_FORMAT` |
| `key` | 长度与 `keyBits` 匹配，`^[0-9a-f]+$` | `400 E_KEY_LENGTH` |
| `keyBits` | ∈ {128,192,256} | `422`（Pydantic 枚举） |

十六进制统一小写后再运算；大小写混入时先 `.lower()` 再校验。

---

## 6. 算法实现规格（`backend/app/core/aes/`）

### 6.1 S 盒与常量（`sbox.py`）
- `SBOX: list[int]` 长度 256，`INV_SBOX: list[int]` 长度 256，`RCON: list[int]`（`0x01,0x02,0x04,...,0x36`）。
- 生产代码**硬编码 FIPS-197 标准表**；推导式仅在测试中用作对照（见下）。
- 提供 `sub_byte(b) -> int`、`inv_sub_byte(b) -> int`。

推导式（仅测试用，用于证明硬编码表正确）：

```python
def _inv(a):                       # GF(2^8) 乘法逆元，a=0 时返回 0
    for x in range(1, 256):
        if gmul(a, x) == 1: return x

def build_sbox() -> list[int]:     # 仿射变换后异或 0x63
    s = []
    for a in range(256):
        b = _inv(a)
        s.append(b ^ rotl8(b,1) ^ rotl8(b,2) ^ rotl8(b,3) ^ rotl8(b,4) ^ 0x63)
    return s
```

**已核对的锚点值**（任何实现都必须先通过这 5 条，否则后面全错）：

| 表达式 | 期望值 |
|---|---|
| `SBOX[0x00]` | `0x63` |
| `SBOX[0x01]` | `0x7c` |
| `SBOX[0x53]` | `0xed` |
| `SBOX[0x19]` | `0xd4` |
| `INV_SBOX[0xd4]` | `0x19` |

### 6.2 GF(2^8)（`gf.py`）
```python
def xtime(b: int) -> int          # 左移一位，溢出则异或 0x1b
def gmul(a: int, b: int) -> int   # 俄罗斯农民乘法，模 x^8+x^4+x^3+x+1
```
- 断言：`gmul(0x57, 0x83) == 0xc1`、`gmul(0x57, 0x13) == 0xfe`。

### 6.3 密钥扩展（`key_expansion.py`）
- `expand_key(key: bytes, nk: int, nr: int) -> list[list[int]]`，返回 `(4*(nr+1))` 个 4 字节字。
- 逐字生成时必须记录 `detail`（rotWord / subWord / rcon / xor），用于 R3 可视化。
- 条件：`if i % nk == 0` 时 `RotWord → SubWord → XOR Rcon`；AES-256 额外 `if i % nk == 4` 时只做 `SubWord`。

### 6.4 轮函数（`rounds.py`）
每个函数接受 `state: list[list[int]]`（4×4，`state[r][c]`）并返回**新的** state（不可原地修改，便于生成 before/after）。

- `sub_bytes` / `inv_sub_bytes`
- `shift_rows`：第 r 行左移 r（`inv` 为右移 r）
- `mix_columns`：每列左乘固定矩阵；`inv_mix_columns` 用 `0e 0b 0d 09`
- `add_round_key(state, round_key)`：逐字节异或

每个函数同时产出 `cells` 明细（由 `engine.py` 组装），`aux` 字段填写规则：

| 操作 | `aux` 内容 |
|---|---|
| SubBytes | `f"sbox[{x:02x}]"` |
| InvSubBytes | `f"inv_sbox[{x:02x}]"` |
| ShiftRows / InvShiftRows | `f"from r{r}c{c0}"` 说明来源格 |
| MixColumns | `f"xtime({a:02x})={xt:02x}"` |
| AddRoundKey | 轮密钥字节 `f"{k:02x}"` |

### 6.5 引擎入口（`engine.py`）
```python
def build_trace(input_hex: str, key_hex: str, key_bits: int, mode: str) -> Trace
```
- 纯函数，不抛业务异常以外的错误；不做 IO；可被并发调用。
- 状态展平遵循**列主序**：`state[r][c] -> flat[4*c + r]`，即按输入字节顺序每 4 字节填满一列。
  必须写测试验证：输入 `00112233445566778899aabbccddeeff` 时
  `state[0][0]==0x00`、`state[1][0]==0x11`、`state[2][0]==0x22`、`state[3][0]==0x33`、`state[0][1]==0x44`。
  （最常见的错误是按行填满，会使对拍在第一个字节之后全部不符——先写这条测试再写算法。）

---

## 7. 后端实现（FastAPI）

### 7.1 接口清单（路径与鉴权不可改）

| 方法 | 路径 | 请求体/参数 | 返回 | 鉴权 |
|---|---|---|---|---|
| POST | `/api/auth/register` | `{username, password}` | `{id, username}` | 否 |
| POST | `/api/auth/login` | `{username, password}` | `{access_token, token_type, user}` | 否 |
| GET | `/api/user/me` | — | `{id, username, role, created_at}` | 是 |
| POST | `/api/crypto/aes` | `{input, key, keyBits, mode}` | `Trace` | 可选 |
| GET | `/api/crypto/sbox` | `?inverse=false` | `{table: number[16][16]}` | 否 |
| GET | `/api/history/sessions` | `?page=1&size=20` | `{items: [...], total, page, size}` | 是 |
| GET | `/api/history/sessions/{id}` | — | `Trace` + 元信息 | 是 |
| DELETE | `/api/history/sessions/{id}` | — | `204` | 是 |
| POST | `/api/exercise/generate` | `{type, difficulty}` | `{exercise_id, type, prompt, snapshot}` | 是 |
| POST | `/api/exercise/submit` | `{exercise_id, answer}` | `{is_correct, expected, analysis, step_index}` | 是 |
| POST | `/api/ai/tutor/chat` | `{session_id?, step_context, question}` | SSE 流 | 是 |

**统一响应包装**：除 SSE 外，全部返回 `{code: 0, message: "ok", data: <payload>}`；错误时 `code` 为业务码，`message` 为中文提示，HTTP 状态码同步（400/401/403/404/429/500）。

**错误码表**（写进 `core/errors.py`）：

```
E_INPUT_FORMAT  E_KEY_LENGTH  E_AUTH_FAILED  E_TOKEN_INVALID
E_USER_EXISTS   E_NOT_FOUND   E_FORBIDDEN    E_RATE_LIMITED
E_AI_UNAVAILABLE
```

### 7.2 数据表（`app/models/`）

```python
class User:            # users
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=32)
    password_hash: str
    role: str = Field(default="student")   # student | admin
    created_at: datetime

class CryptoSession:   # crypto_sessions
    id, user_id (FK, nullable), algorithm, mode, key_bits
    input_hex, key_hex, output_hex, rounds
    trace_json: str          # 完整 Trace 序列化，回放用
    created_at

class Exercise:        # exercises
    id, type, difficulty, snapshot_json, expected, analysis, step_index, created_at

class ExerciseAttempt: # exercise_attempts
    id, user_id, exercise_id, answer, is_correct, created_at

class AiConversation:  # ai_conversations
    id, user_id, session_id (nullable), created_at

class AiMessage:       # ai_messages
    id, conversation_id, role, content, created_at
```

- `trace_json` 用 `json.dumps(..., ensure_ascii=False)`，读取时 `json.loads` 后交给 Pydantic 校验。
- 越权规则：`GET/DELETE /api/history/sessions/{id}` 中 `session.user_id != current_user.id` 时返回 **404**（不暴露存在性）。
- 建表用 `SQLModel.metadata.create_all`（本期不引入 Alembic，可在设计文档中说明理由）。

### 7.3 练习模式（`services/exercise.py`）

服务端基于**真实 Trace** 生成题目，三种题型：

| type | 生成方式 | answer 格式 | 判分 |
|---|---|---|---|
| `step_identify` | 随机取一步，给出 `stateBefore`/`stateAfter`，四选一（正确 op + 3 个干扰 op） | `"SubBytes"` 等字符串 | 等值比较 |
| `cell_result` | 随机取一步，指定一个 `(r,c)`，问变换后字节值 | 2 位 hex 字符串 | 小写化后比较 |
| `key_param` | 固定明文，随机两个密钥，问"哪一轮输出首次出现差异"或指定字节值 | 整数轮次或 2 位 hex | 按题型比较 |

- 干扰项必须从实际出现过的 op 集合中取，不能凭空造。
- 答错时必须返回 `analysis`（含正确推导过程中文说明）与 `step_index`，前端据此跳转到对应动画步。
- 题目落库保存，`submit` 时按 `exercise_id` 取回标准答案，**不得信任前端传来的 expected**。

### 7.4 安全中间件

| 措施 | 实现 |
|---|---|
| 输入校验 | 全部请求体走 Pydantic；hex 字段用 `pattern` 约束 |
| XSS | 后端不渲染 HTML；前端禁用 `v-html` 渲染用户/AI 内容；响应头 `Content-Security-Policy: default-src 'self'` |
| CSRF | 令牌放 `Authorization: Bearer`，不使用 Cookie；写操作校验 `Origin` 头在白名单内 |
| 安全响应头 | `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer` |
| 限流 | AI 接口按用户 20 次/分钟，内存字典 + 时间窗即可；超限 `429 E_RATE_LIMITED` |
| 口令 | `passlib` bcrypt，cost=12；不记录明文口令到日志 |

---

## 8. AI 辅导模块

### 8.1 Provider 适配层（`services/ai/provider.py`）

```python
class ChatProvider(Protocol):
    async def stream(self, messages: list[Message]) -> AsyncIterator[str]: ...

def get_provider() -> ChatProvider   # 依环境变量选择
```

环境变量：`AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL`、`AI_TIMEOUT=10`、`AI_ENABLED=true`。
实现一个 `OpenAICompatProvider`（POST `{AI_BASE_URL}/chat/completions`，`stream=true`，逐行解析 `data: ` 前缀）。**不绑定具体厂商**。

### 8.2 提示词组装（`services/ai/prompt.py`）

固定三段式，模板写入代码常量，禁止拼接用户可控的 system 内容：

```
【角色】你是密码学助教，面向零基础本科生讲解 AES。要求：结合当前步骤的具体字节讲解，
       多用类比，单次回答不超过 200 字，不使用未解释的术语，不给完整练习答案。
【上下文】算法：AES-{keyBits}｜模式：{encrypt|decrypt}｜当前：第 {round} 轮 {op}（第 {index+1}/{total} 步）
       输入状态：{stateBefore 每 2 位空格分隔}
       输出状态：{stateAfter}
       本次变化：{cells 前 4 项，格式 "r0c0: 19→d4 (sbox[19])"}
【历史】最近 6 条消息（超出丢弃最早）
【问题】{用户输入}
```

`step_context` 由前端传入 `{index, round, op, stateBefore, stateAfter, cells}`，后端**必须校验**其与 `index` 一致且 hex 格式合法（防止注入超长内容）。

### 8.3 上下文管理

- 会话表存全量消息；组装请求时只取**最近 6 条**（3 轮问答）。
- 用户切换步骤时，前端调用时带上新 `step_context`，后端在 messages 中插入一条 `system` 角色提示：`当前已切换至第 X 步`。
- 提供 `POST /api/ai/tutor/chat` 的 `session_id` 为空时新建会话并返回 id。
- 响应格式：`text/event-stream`，每条 `data: {"delta": "..."}`，结束 `data: [DONE]`。

### 8.4 降级（必须实现，必须有测试）

触发条件：`AI_ENABLED=false`、无 `AI_API_KEY`、超时（10s）、HTTP 非 200。
降级行为：直接返回该 step 的 `explain` 字段文案 + 追加一句"（离线讲解：AI 服务暂不可用）"，仍以 SSE 格式输出，前端不区分展示逻辑。

测试 `test_ai_fallback.py` 必须覆盖：无密钥、超时、非 200 三种情况均返回 200 且内容非空。

---

## 9. 前端实现

### 9.1 播放控制器（`stores/player.ts` + `composables/usePlayer.ts`）

状态：`{cursor, status: 'idle'|'playing'|'paused'|'finished', speed: 0.5|1|2|4}`。

动作契约：

| 动作 | 行为 | 断言 |
|---|---|---|
| `play()` | 按 `interval = 1200 / speed` ms 推进 | 到 `steps.length-1` 自动 `finished` |
| `pause()` | 停定时器 | 保留 cursor |
| `next()` / `prev()` | cursor ±1，夹取 `[0, len-1]` | 边界不报错、不越界 |
| `jumpTo(round)` | 定位该轮首个 step 的 index | 找不到时保持不动 |
| `setSpeed(s)` | 改间隔，不清游标 | — |
| `reset()` | cursor=0, status='idle' | — |

**渲染与状态分离**：组件只读 `currentStep = steps[cursor]`，不持有动画中间态。

### 9.2 组件职责

| 组件 | 必须实现 |
|---|---|
| `StateMatrix.vue` | Canvas 绘制 4×4 网格；每格显示 2 位 hex；变化格高亮（`before` 淡色 → `after` 主色，200ms 过渡）；行/列标题 r0-r3、c0-c3；支持 `mode="before"|"after"|"diff"` |
| `SBoxPanel.vue` | 16×16 表格，行列表头为高 4 位/低 4 位；悬停显示 `sbox[0x1a]=0xa2`；点击定位并高亮；支持逆 S 盒切换 |
| `StepTimeline.vue` | 按轮分组的横向时间轴，当前步高亮，点击跳转，显示 `第 n/总 步` |
| `PlayerControls.vue` | 播放/暂停/上一步/下一步/重置/调速下拉/跳轮输入 |
| `KeyScheduleView.vue` | 展示各轮 4 个 word；第 1 轮起展开 `detail` 四步（RotWord→SubWord→Rcon→XOR），高亮参与字节 |
| `AiTutorPanel.vue` | 消息列表、输入框、发送/停止、清空、重试、引用当前步骤；流式增量渲染（`EventSource` 或 `fetch` + ReadableStream） |
| `ExercisePanel.vue` | 题面、选项或输入框、提交、结果与解析、`跳转动画` 按钮 |
| `HistoryList.vue` | 分页列表、点击回放（加载 trace 后进入 Playground 只读模式）、删除二次确认 |

### 9.3 页面

- `/` 首页：项目简介 + 三个入口（可视化演示 / 练习模式 / 我的记录）。
- `/playground`：主工作区。左侧参数与播放控制，中间双状态矩阵 + 时间轴，右侧 AI 辅导面板；`/playground?session=123` 进入回放只读模式。
- `/sbox`：S 盒与逆 S 盒独立页，支持搜索与反查。
- `/exercise`：练习模式，三题型切换。
- `/history`：历史记录（需登录）。
- `/login`：登录与注册。

### 9.4 交互细节硬要求

- 参数调节：明文、密钥输入框支持"文本模式/十六进制模式"切换，文本模式实时转 hex 并显示。
- 修改参数后必须**重新请求** `/api/crypto/aes`，禁止前端本地重算。
- 任一状态矩阵格点击，弹出该字节的完整来历（哪一步、从哪个值来、aux 信息）。
- 播放中切换页面/组件卸载必须 `clearInterval`，防止内存泄漏与幽灵推进。
- AI 面板发送前必须已停在某一步；未加载 Trace 时禁用并提示。

---

## 10. 测试与验收

### 10.1 必过测试

| 测试 | 命令 | 通过标准 |
|---|---|---|
| 算法对拍 | `pytest backend/tests/test_aes_vectors.py -v` | 全部通过 |
| 前端算法 | `pnpm test`（Vitest） | 全部通过 |
| 接口 | `pytest backend/tests/test_api.py -v` | 全部通过 |
| AI 降级 | `pytest backend/tests/test_ai_fallback.py -v` | 3 个场景通过 |

**FIPS-197 对拍向量（必须逐条断言）**：

| 用例 | key | input | expected output |
|---|---|---|---|
| 128 附录B | `2b7e151628aed2a6abf7158809cf4f3c` | `3243f6a8885a308d313198a2e0370734` | `3925841d02dc09fbdc118597196a0b32` |
| 128 全零 | `00000000000000000000000000000000` | `00000000000000000000000000000000` | `66e94bd4ef8a2c3b884cfa59ca342b2e` |
| 192 | `000102030405060708090a0b0c0d0e0f1011121314151617` | `00112233445566778899aabbccddeeff` | `dda97ca4864cdfe06eaf70a0ec0d7191` |
| 256 | `000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f` | `00112233445566778899aabbccddeeff` | `8ea2b7ca516745bfeafc49904b496089` |

> 上述 4 条向量与步数（40/48/56）已用参考实现实测通过，可直接作为开发期的黄金标准。
> 参考实现（单文件、无依赖、含 S 盒推导与对拍）见仓库 `verify/verify_aes.py`，移植时可直接对照。

附加断言：
1. 解密(加密(x)) == x，随机 100 组。
2. 步数正确：128→40，192→48，256→56。
3. 列主序映射正确（见 6.5）。
4. 雪崩：随机 100 组中，改明文任一字节后密文差异位数的**平均值 ≥ 56 位**（理论期望 64 位，单组存在波动，故用均值而非逐组下限）。
5. `MixColumns` 中间量与手算一致：列 `db 13 53 45` → `8e 4d a1 bc`。
6. 越权：用户 A 访问用户 B 的 session 返回 404。
7. XSS：用户名传 `<script>alert(1)</script>` 后，接口返回与页面渲染均为原样文本，不执行。

### 10.2 功能验收清单（`docs/status.md` 逐项勾选）

```
[ ] AES-128/192/256 加密 Trace 正确（对拍通过）
[ ] AES 解密 Trace 正确且为加密逆序
[ ] SubBytes 动画 + S 盒高亮
[ ] InvSubBytes 动画 + 逆 S 盒高亮
[ ] ShiftRows 动画（含来源轨迹）
[ ] InvShiftRows 动画
[ ] MixColumns 动画（含 xtime 过程）
[ ] InvMixColumns 动画
[ ] AddRoundKey 动画（含初始轮）
[ ] 状态矩阵 4×4 渲染 + 逐格高亮
[ ] 密钥扩展全流程可视化（含 detail 四步）
[ ] 播放 / 暂停 / 单步前进 / 单步后退 / 跳轮 / 调速 / 重置
[ ] 参数调节（明文、密钥、密钥长度、模式）后重新生成
[ ] 文本↔十六进制输入互转
[ ] 单格点击查看字节来历
[ ] AI 步骤讲解（停在任何一步都能问答）
[ ] AI 多轮对话（上下文连贯）
[ ] AI 降级（无密钥/超时/500）
[ ] 注册 / 登录 / JWT 鉴权
[ ] 历史记录：保存 / 列表 / 回放 / 删除
[ ] 越权访问返回 404
[ ] 练习：step_identify 出题 + 判分 + 解析
[ ] 练习：cell_result 出题 + 判分 + 解析
[ ] 练习：key_param 出题 + 判分 + 解析
[ ] 答错后可跳转到对应动画步
[ ] 安全响应头 + CSP
[ ] 输入校验（非法 hex、超长、错长度）
[ ] 限流生效（第 21 次返回 429）
[ ] Docker 一键启动
[ ] 已部署，公网可访问
[ ] docs/ 三份文档齐备
[ ] CI/CD 流水线跑通（构建+测试+部署）
```

### 10.3 完成定义（DoD，每个 PR 都要满足）

1. 代码合入 `develop` 且流水线绿。
2. Chrome 与 Edge 手动验证通过。
3. 新增接口出现在 `/docs` 且可调试。
4. 涉及输入的界面已自测非法输入。
5. 对应测试用例已加入 `docs/test-report.md` 并有执行结果。
6. `docs/status.md` 已更新勾选。

---

## 11. 决策优先级（遇到歧义时按此顺序）

1. 任务书 R1–R13 的明确要求优先。
2. 本文件第 5、6、7 节的数据契约与接口签名优先于任何"更优雅"的设计。
3. 可视化正确性 > 动画美观度。
4. 功能完整 > 代码优雅。
5. 可演示性 > 可扩展性。
6. 若某选做功能与必做项冲突，**直接砍掉选做**，不要压缩必做项时间。

---

## 12. 关键风险与对策

| 风险 | 触发信号 | 对策 |
|---|---|---|
| 契约反复变更导致返工 | 第 1 周内 `trace.ts` 改动 > 2 次 | 冻结 v1.0，之后只允许加可选字段 |
| 动画性能差 | 矩阵重绘整屏 > 16ms | 只重绘变化格，离屏 Canvas 缓存静态层 |
| AI 不可用 | 请求超时/401 | 走降级分支；演示前录屏备份 |
| 列主序搞错导致全盘错误 | 对拍第一位就不一致 | 先写 `test_column_major`，再做可视化 |
| 解密逆向顺序写错 | 解密对拍失败 | 用加密 steps 反序 + Inv op 映射，写单元测试固定 |
| CodeArts 权限/额度未就绪 | 第 1 天无法建仓 | 开工前完成账号申请；本地 Git 先跑，后补推送 |

---

## 13. 交付物清单（缺一不可）

| 项 | 路径/形式 |
|---|---|
| 源码仓库 | CodeArts 项目，含分支与 MR 记录 |
| 可运行平台 | 部署 URL + 演示账号 |
| 需求文档 | `docs/requirement.md` |
| 设计文档 | `docs/design.md`（含架构图、Trace 契约、接口表、表结构） |
| 部署文档 | `docs/deploy.md`（环境变量、步骤、回滚） |
| 测试报告 | `docs/test-report.md` |
| 流水线定义 | `.codearts/pipeline.yml` |
| 答辩 PPT | 独立文件 |

---

## 14. 立即开始的第一步

```
1. 创建第 4 节目录结构，初始化前后端工程
2. 实现 backend/app/core/aes/{sbox,gf,key_expansion,rounds,engine}.py
3. 实现 backend/tests/test_aes_vectors.py 并跑通（此时还没有任何 UI）
4. 冻结 docs/contracts/trace.md 与 frontend/src/types/trace.ts
5. 实现 StateMatrix.vue 静态渲染，用固定 Trace 打样
6. 在此基础上按第 7、9 节顺序开发
```

**顺序不可颠倒**：算法与契约先于 UI，UI 先于 AI，AI 先于练习模式。每一层跑通再进入下一层。