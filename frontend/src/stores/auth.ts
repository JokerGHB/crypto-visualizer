/** 认证状态 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { fetchMe, login as loginApi, register as registerApi } from '../api/auth';
import type { PublicUser } from '../api/auth';
import { getToken, setToken } from '../api/client';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<PublicUser | null>(null);
  const token = ref<string | null>(getToken());
  const loading = ref(false);
  const error = ref<string | null>(null);

  const isLoggedIn = computed(() => Boolean(token.value && user.value));

  /** 应用启动时尝试恢复登录态 */
  async function restore(): Promise<void> {
    if (!token.value) {
      return;
    }
    try {
      user.value = await fetchMe();
    } catch {
      // 令牌失效，静默清除
      logout();
    }
  }

  async function login(username: string, password: string): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const result = await loginApi(username, password);
      token.value = result.accessToken;
      setToken(result.accessToken);
      user.value = result.user;
    } catch (err) {
      error.value = (err as Error).message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function register(username: string, password: string): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      await registerApi(username, password);
      await login(username, password);
    } catch (err) {
      error.value = (err as Error).message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  function logout(): void {
    user.value = null;
    token.value = null;
    setToken(null);
  }

  return { user, token, loading, error, isLoggedIn, restore, login, register, logout };
});