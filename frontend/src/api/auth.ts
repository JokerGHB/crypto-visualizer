/** 认证接口 */

import { api } from './client';

export interface PublicUser {
  id: number;
  username: string;
  role: string;
  createdAt: string;
}

export interface LoginResult {
  accessToken: string;
  tokenType: string;
  user: PublicUser;
}

export function register(username: string, password: string): Promise<PublicUser> {
  return api.post<PublicUser>('/api/auth/register', { username, password });
}

export function login(username: string, password: string): Promise<LoginResult> {
  return api.post<LoginResult>('/api/auth/login', { username, password });
}

export function fetchMe(): Promise<PublicUser> {
  return api.get<PublicUser>('/api/auth/me', true);
}