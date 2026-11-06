# Trace 数据契约 v1.0

本文件是前后端共用的唯一权威定义，已冻结。

- 后端实现：`backend/app/schemas/trace.py`（定义 snake_case，序列化为 camelCase）
- 前端镜像：`frontend/src/types/trace.ts`
- 版本：v1.0　冻结日期：项目第 1 阶段

## 变更规则

1. 已发布字段**不得改名、不得改类型**。
2. 新增字段必须是**可选**字段（有默认值），保证旧数据仍可解析。
3. 任何破坏性变更须同步修改两处实现与本文档，并在 MR 描述中标注 `BREAKING`。

## 字段

### Trace

| 字段 | 类型 | 说明 |
|---|---|---|
| `algorithm` | `string` | 固定 `"AES"` |
| `keyBits` | `128 \| 192 \| 256` | 密钥长度 |
| `mode` | `"encrypt" \| "decrypt"` | 运算方向 |
| `rounds` | `number` | 10 / 12 / 14 |
| `input` | `string` | 32 位小写十六进制 |
| `key` | `string` | 32 / 48 / 64 位小写十六进制 |
| `output` | `string` | 32 位小写十六进制 |
| `keySchedule` | `KeyScheduleRound[]` | 长度 `rounds + 1` |
| `steps` | `Step[]` | 长度见下表 |

### Step

| 字段 | 类型 | 说明 |
|---|---|---|
| `index` | `number` | 等于数组下标 |
| `round` | `number` | 0..Nr |
| `op` | `AesOp` | 操作类型 |
| `stateBefore` | `string` | 32 位十六进制，列主序 |
| `stateAfter` | `string` | 32 位十六进制，列主序 |
| `roundKey` | `string \| null` | 仅 `AddRoundKey` 非空 |
| `cells` | `CellChange[]` | 恒为 16 项，覆盖全部字节位置 |
| `explain` | `string` | 中文说明，AI 降级时直接使用 |

### CellChange

| 字段 | 类型 | 说明 |
|---|---|---|
| `row` / `col` | `number` | 0..3 |
| `before` / `after` | `string` | 2 位小写十六进制 |
| `aux` | `string \| null` | 见下表 |

### KeyScheduleRound / KeyScheduleDetail

`words` 恒为 4 项。`detail` 仅在 `i % nk == 0`（AES-256 另含 `i % nk == 4`）对应的轮次非空，
因此**并非每轮都有 detail**，已实测分布：

| 密钥长度 | nk | 有 detail 的轮次 |
|---|---|---|
| 128 | 4 | 1..10 |
| 192 | 6 | 1, 3, 4, 6, 7, 9, 10, 12 |
| 256 | 8 | 2..14 |

## 不变量（已由测试强制）

1. `steps[0].stateBefore === input`
2. `steps[steps.length-1].stateAfter === output`
3. 对任意相邻两步：`steps[i].stateAfter === steps[i+1].stateBefore`
4. `steps[i].index === i`
5. 每个 Step 的 `cells.length === 16`
6. 步数：128→40，192→48，256→56；解密同长

## 列主序

状态展平规则为列主序：`flat[4*c + r] === state[r][c]`。

输入 `00112233445566778899aabbccddeeff` 时：

```
state[0][0]=0x00  state[1][0]=0x11  state[2][0]=0x22  state[3][0]=0x33
state[0][1]=0x44  state[1][1]=0x55  ...
```

## aux 字段取值规则

| 操作 | aux 内容 |
|---|---|
| SubBytes | `sbox[19]` |
| InvSubBytes | `inv_sbox[d4]` |
| ShiftRows / InvShiftRows | `from r1c2` |
| MixColumns | `xtime(db)=b3` 或 `gf_mul(...)` |
| AddRoundKey | 轮密钥字节，如 `2b` |

## 示例

```json
{
  "index": 1,
  "round": 1,
  "op": "SubBytes",
  "stateBefore": "193de3bea0f4e22b9ac68d2ae9f84808",
  "stateAfter": "d42711aee0bf98f1b8b45de51e415230",
  "roundKey": null,
  "cells": [{ "row": 0, "col": 0, "before": "19", "after": "d4", "aux": "sbox[19]" }],
  "explain": "第 1 轮 SubBytes：字节替代，每个字节查 S 盒完成非线性替换"
}
```