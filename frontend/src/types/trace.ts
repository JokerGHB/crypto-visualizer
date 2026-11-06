/**
 * Trace 数据契约：与后端 backend/app/schemas/trace.py 逐字段对应。
 *
 * 后端以 snake_case 定义、序列化为 camelCase；本文件即线上契约字段名。
 * 字段一旦发布只允许新增可选字段，不得改名或改类型。
 * 权威文档：docs/contracts/trace.md
 */

export type AesKeyBits = 128 | 192 | 256;

export type AesMode = 'encrypt' | 'decrypt';

export type AesOp =
  | 'AddRoundKey'
  | 'SubBytes'
  | 'ShiftRows'
  | 'MixColumns'
  | 'InvSubBytes'
  | 'InvShiftRows'
  | 'InvMixColumns';

/** 状态矩阵中单个字节的变化明细 */
export interface CellChange {
  /** 行号 0..3 */
  row: number;
  /** 列号 0..3 */
  col: number;
  /** 变化前字节，2 位小写十六进制 */
  before: string;
  /** 变化后字节，2 位小写十六进制 */
  after: string;
  /** 辅助信息：轮密钥字节 / sbox 坐标 / xtime 中间量 */
  aux: string | null;
}

/** 可视化的最小单位：一次操作及其前后状态 */
export interface Step {
  /** 步骤序号，等于其在 steps 数组中的下标 */
  index: number;
  /** 轮次 0..Nr */
  round: number;
  op: AesOp;
  /** 操作前状态，32 位小写十六进制，列主序展平 */
  stateBefore: string;
  /** 操作后状态，32 位小写十六进制，列主序展平 */
  stateAfter: string;
  /** 仅 AddRoundKey 步存在 */
  roundKey: string | null;
  /** 逐格明细，恒为 16 项 */
  cells: CellChange[];
  /** 一句话中文说明，AI 不可用时的本地讲解 */
  explain: string;
}

/** 密钥扩展中 RotWord / SubWord / Rcon / XOR 四步明细 */
export interface KeyScheduleDetail {
  rotWord: string;
  subWord: string;
  rcon: string;
  xor: string;
}

/** 密钥扩展中一轮的结果 */
export interface KeyScheduleRound {
  round: number;
  /** 该轮 4 个 8 位十六进制字 */
  words: string[];
  /** 并非每轮都有；分布见 docs/contracts/trace.md */
  detail: KeyScheduleDetail | null;
}

/** 一次 AES 运算的完整轨迹 */
export interface Trace {
  algorithm: string;
  keyBits: AesKeyBits;
  mode: AesMode;
  /** 10 / 12 / 14 */
  rounds: number;
  input: string;
  key: string;
  output: string;
  keySchedule: KeyScheduleRound[];
  steps: Step[];
}

/** POST /api/crypto/aes 的请求体 */
export interface AesRequest {
  input: string;
  key: string;
  keyBits: AesKeyBits;
  mode: AesMode;
}

/**
 * 后端统一响应包装。
 * 成功时 code 为数字 0，失败时后端返回字符串错误码（如 E_KEY_LENGTH），
 * 因此这里用联合类型，调用方需先判分支。
 */
export interface ApiEnvelope<T> {
  code: number | string;
  message: string;
  data: T;
}

/** 历史记录列表项 */
export interface SessionSummary {
  id: number;
  algorithm: string;
  mode: AesMode;
  keyBits: AesKeyBits;
  input: string;
  key: string;
  output: string;
  rounds: number;
  createdAt: string;
}

/** 分页结果 */
export interface PagedResult<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

/** 练习题 */
export interface Exercise {
  exerciseId: number;
  type: string;
  difficulty: string;
  prompt: string;
  snapshot: Record<string, unknown>;
}

/** 判分结果 */
export interface ExerciseResult {
  isCorrect: boolean;
  expected: string;
  analysis: string;
  stepIndex: number | null;
  type: string;
}

/** 操作类型的中文名 */
export const OP_LABELS: Record<AesOp, string> = {
  AddRoundKey: '轮密钥加',
  SubBytes: '字节替代',
  ShiftRows: '行移位',
  MixColumns: '列混合',
  InvSubBytes: '逆字节替代',
  InvShiftRows: '逆行移位',
  InvMixColumns: '逆列混合',
};

/**
 * 把 32 位十六进制字符串拆成 4×4 字节矩阵（列主序）。
 * flat[4*c + r] === matrix[r][c]
 */
export function hexToMatrix(hex: string): string[][] {
  if (!/^[0-9a-f]{32}$/.test(hex)) {
    throw new Error(`状态字符串必须是 32 位小写十六进制，收到：${hex}`);
  }
  const matrix: string[][] = [[], [], [], []];
  for (let c = 0; c < 4; c += 1) {
    for (let r = 0; r < 4; r += 1) {
      matrix[r][c] = hex.slice((4 * c + r) * 2, (4 * c + r) * 2 + 2);
    }
  }
  return matrix;
}

/** 把 4×4 字节矩阵（列主序）还原成 32 位十六进制字符串 */
export function matrixToHex(matrix: string[][]): string {
  const parts: string[] = [];
  for (let c = 0; c < 4; c += 1) {
    for (let r = 0; r < 4; r += 1) {
      parts.push(matrix[r][c]);
    }
  }
  return parts.join('');
}

/** 字节值映射到色相，用于矩阵色阶 */
export function byteColor(byteHex: string): string {
  const value = parseInt(byteHex, 16);
  return `hsl(${Math.round((value / 255) * 260)}, 62%, 58%)`;
}