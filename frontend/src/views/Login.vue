<script setup lang="ts">
/** 登录 / 注册页 */
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const mode = ref<'login' | 'register'>('login');
const username = ref('');
const password = ref('');
const confirm = ref('');
const localError = ref<string | null>(null);

const isRegister = computed(() => mode.value === 'register');

const canSubmit = computed(() => {
  if (!username.value.trim() || !password.value) {
    return false;
  }
  if (isRegister.value) {
    if (username.value.trim().length < 3) {
      return false;
    }
    if (password.value.length < 6) {
      return false;
    }
    return password.value === confirm.value;
  }
  return true;
});

function toggleMode(): void {
  mode.value = isRegister.value ? 'login' : 'register';
  localError.value = null;
  confirm.value = '';
}

async function submit(): Promise<void> {
  if (!canSubmit.value) {
    return;
  }
  localError.value = null;
  try {
    if (isRegister.value) {
      await auth.register(username.value.trim(), password.value);
    } else {
      await auth.login(username.value.trim(), password.value);
    }
    const redirect = route.query.redirect;
    await router.push(typeof redirect === 'string' ? redirect : '/playground');
  } catch (err) {
    localError.value = (err as Error).message;
  }
}
</script>

<template>
  <div class="login-view">
    <div class="card">
      <h1>{{ isRegister ? '注册账号' : '登录' }}</h1>
      <p class="sub">
        {{ isRegister ? '注册后可保存历史记录、使用练习模式。' : '登录后可保存加解密记录并使用练习模式。' }}
      </p>

      <label class="field">
        <span>用户名</span>
        <input
          v-model="username"
          type="text"
          maxlength="32"
          autocomplete="username"
          placeholder="3-32 位字母、数字、下划线或中文"
          @keyup.enter="submit"
        />
      </label>

      <label class="field">
        <span>口令</span>
        <input
          v-model="password"
          type="password"
          maxlength="72"
          :autocomplete="isRegister ? 'new-password' : 'current-password'"
          :placeholder="isRegister ? '至少 6 位' : '请输入口令'"
          @keyup.enter="submit"
        />
      </label>

      <label v-if="isRegister" class="field">
        <span>确认口令</span>
        <input
          v-model="confirm"
          type="password"
          maxlength="72"
          autocomplete="new-password"
          placeholder="再输入一次"
          @keyup.enter="submit"
        />
      </label>

      <p v-if="isRegister && confirm && password !== confirm" class="warn">两次输入的口令不一致</p>
      <p v-if="localError || auth.error" class="error">{{ localError ?? auth.error }}</p>

      <button type="button" class="btn primary" :disabled="!canSubmit || auth.loading" @click="submit">
        {{ auth.loading ? '处理中…' : isRegister ? '注册并登录' : '登录' }}
      </button>

      <p class="switch">
        {{ isRegister ? '已有账号？' : '还没有账号？' }}
        <button type="button" class="link" @click="toggleMode">
          {{ isRegister ? '去登录' : '去注册' }}
        </button>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-view {
  display: flex;
  justify-content: center;
  padding: 56px 20px;
}

.card {
  width: 100%;
  max-width: 380px;
  padding: 28px 26px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
}

h1 {
  margin: 0 0 8px;
  font-size: 21px;
  color: #111827;
}

.sub {
  margin: 0 0 22px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #6b7280;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 14px;
}

.field span {
  font-size: 12px;
  color: #6b7280;
}

.field input {
  padding: 9px 11px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13.5px;
  outline: none;
}

.field input:focus {
  border-color: #a5b4fc;
}

.btn {
  width: 100%;
  margin-top: 6px;
  padding: 10px;
  border: none;
  border-radius: 9px;
  background: #4f46e5;
  color: #ffffff;
  font-size: 13.5px;
  cursor: pointer;
}

.btn:disabled {
  background: #c7d2fe;
  cursor: not-allowed;
}

.warn {
  margin: 0 0 10px;
  font-size: 12px;
  color: #b45309;
}

.error {
  margin: 0 0 10px;
  font-size: 12px;
  color: #b91c1c;
}

.switch {
  margin: 16px 0 0;
  text-align: center;
  font-size: 12.5px;
  color: #6b7280;
}

.link {
  border: none;
  background: none;
  color: #4f46e5;
  cursor: pointer;
  font-size: 12.5px;
  padding: 0;
}
</style>