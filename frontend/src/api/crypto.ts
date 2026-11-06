/** 加密相关接口 */

import { api } from './client';
import type { AesRequest, Trace } from '../types/trace';

/** 执行 AES 加/解密，返回完整 Trace */
export function computeAes(payload: AesRequest): Promise<Trace> {
  // 已登录时后端会自动记录历史；request 层按需带令牌
  return api.post<Trace>('/api/crypto/aes', payload, true);
}

/** 获取 S 盒或逆 S 盒 */
export function fetchSBox(inverse = false): Promise<{ inverse: boolean; table: number[][] }> {
  return api.get<{ inverse: boolean; table: number[][] }>(
    `/api/crypto/sbox?inverse=${inverse}`,
  );
}