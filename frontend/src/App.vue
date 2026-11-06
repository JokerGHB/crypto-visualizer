<script setup lang="ts">
/** 应用外壳：顶部导航 + 路由出口 */
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from './stores/auth';

const auth = useAuthStore();
const router = useRouter();

const nav = [
  { to: '/', label: '首页' },
  { to: '/playground', label: '可视化演示' },
  { to: '/sbox', label: 'S 盒' },
  { to: '/exercise', label: '练习模式' },
  { to: '/history', label: '我的记录' },
];

function logout(): void {
  auth.logout();
  void router.push('/');
}

onMounted(() => {
  void auth.restore();
});
</script>

<template>
  <div class="app">
    <header class="topbar">
      <div class="brand" @click="router.push('/')">
        <span class="logo">AES</span>
        <span class="name">密码学可视化教学平台</span>
      </div>

      <nav class="nav">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          active-class="active"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="user">
        <template v-if="auth.isLoggedIn">
          <span class="username">{{ auth.user?.username }}</span>
          <button type="button" class="btn small" @click="logout">退出</button>
        </template>
        <button
          v-else
          type="button"
          class="btn small primary"
          @click="router.push('/login')"
        >
          登录
        </button>
      </div>
    </header>

    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.topbar {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 20px;
  height: 56px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 20;
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  flex-shrink: 0;
}

.logo {
  padding: 3px 8px;
  background: #4f46e5;
  color: #ffffff;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.name {
  font-size: 13.5px;
  font-weight: 600;
  color: #111827;
  white-space: nowrap;
}

.nav {
  display: flex;
  gap: 4px;
  flex: 1;
  overflow-x: auto;
}

.nav-link {
  padding: 6px 12px;
  border-radius: 7px;
  font-size: 12.5px;
  color: #6b7280;
  text-decoration: none;
  white-space: nowrap;
}

.nav-link:hover {
  background: #f3f4f6;
  color: #374151;
}

.nav-link.active {
  background: #eef2ff;
  color: #4338ca;
  font-weight: 600;
}

.user {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.username {
  font-size: 12.5px;
  color: #4b5563;
}

.btn {
  padding: 6px 14px;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  background: #ffffff;
  color: #374151;
  font-size: 12.5px;
  cursor: pointer;
}

.btn.small {
  padding: 5px 12px;
  font-size: 12px;
}

.btn.primary {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #ffffff;
}

.content {
  flex: 1;
}

@media (max-width: 720px) {
  .name {
    display: none;
  }
}
</style>