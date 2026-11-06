/**
 * HTTP 客户端：统一处理令牌、错误包装与超时。
 *
 * 所有接口返回 {code, message, data}；本层在 code !== 0 时抛 ApiError，
 * 业务代码只需处理 data。
 */

import type { ApiEnvelope } from '../types/trace';

/**
 * 默认走相对路径：开发期由 Vite 的 /api 代理转发到后端，
 * 生产期由同源反向代理处理，因此前端无需硬编码后端地址。
 * 若前后端分离部署，设置 VITE_API_BASE_URL 覆盖即可。
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

const TOKEN_KEY = 'crypto_visualizer_token';

/** 业务错误 */
export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code = 'E_INTERNAL', status = 0) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE';
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
}

/** 发起请求并解包 data 字段 */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = false, signal } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (auth) {
    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') {
      throw err;
    }
    throw new ApiError('无法连接服务器，请确认后端已启动', 'E_NETWORK');
  }

  // 204 无响应体
  if (response.status === 204) {
    return undefined as T;
  }

  let payload: ApiEnvelope<T> | null = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text) as ApiEnvelope<T>;
    } catch {
      throw new ApiError('服务器返回内容无法解析', 'E_PARSE', response.status);
    }
  }

  if (!response.ok || (payload && payload.code !== 0)) {
    throw new ApiError(
      payload?.message ?? `请求失败（HTTP ${response.status}）`,
      typeof payload?.code === 'string' ? payload.code : 'E_INTERNAL',
      response.status,
    );
  }

  return payload!.data;
}

export const api = {
  get<T>(path: string, auth = false): Promise<T> {
    return request<T>(path, { method: 'GET', auth });
  },
  post<T>(path: string, body: unknown, auth = false): Promise<T> {
    return request<T>(path, { method: 'POST', body, auth });
  },
  del<T>(path: string, auth = false): Promise<T> {
    return request<T>(path, { method: 'DELETE', auth });
  },
};

/** SSE 流式 POST：逐块回调文本增量 */
export async function streamPost(
  path: string,
  body: unknown,
  onDelta: (delta: string) => void,
  onConversation?: (id: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken();
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const text = await response.text();
    let message = `请求失败（HTTP ${response.status}）`;
    try {
      message = (JSON.parse(text) as { message?: string }).message ?? message;
    } catch {
      // 保持默认提示
    }
    throw new ApiError(message, 'E_STREAM', response.status);
  }
  if (!response.body) {
    throw new ApiError('服务器未返回流式内容', 'E_STREAM');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    // SSE 以空行分隔事件
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf('\n\n');

      for (const line of rawEvent.split('\n')) {
        if (!line.startsWith('data: ')) {
          continue;
        }
        const data = line.slice(6).trim();
        if (data === '[DONE]') {
          return;
        }
        try {
          const parsed = JSON.parse(data) as {
            delta?: string;
            conversationId?: number;
          };
          if (typeof parsed.conversationId === 'number' && onConversation) {
            onConversation(parsed.conversationId);
          }
          if (typeof parsed.delta === 'string') {
            onDelta(parsed.delta);
          }
        } catch {
          // 忽略无法解析的帧
        }
      }
    }
  }
}