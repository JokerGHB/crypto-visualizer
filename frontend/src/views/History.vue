<script setup lang="ts">
/** 历史记录页：分页列表、回放入口、删除确认 */
import { computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { deleteSession, listSessions } from '../api/history';
import { useAuthStore } from '../stores/auth';
import type { SessionSummary } from '../types/trace';

const router = useRouter();
const auth = useAuthStore();

const items = ref<SessionSummary[]>([]);
const total = ref(0);
const page = ref(1);
const size = 10;
const loading = ref(false);
const error = ref<string | null>(null);
const pendingDelete = ref<number | null>(null);

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size)));

async function load(): Promise<void> {
  if (!auth.isLoggedIn) {
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const result = await listSessions(page.value, size);
    items.value = result.items;
    total.value = result.total;
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    loading.value = false;
  }
}

async function gotoPage(next: number): Promise<void> {
  if (next < 1 || next > totalPages.value) {
    return;
  }
  page.value = next;
  await load();
}

function replay(id: number): void {
  router.push({ path: '/playground', query: { session: String(id) } });
}

async function confirmDelete(id: number): Promise<void> {
  try {
    await deleteSession(id);
    pendingDelete.value = null;
    // 删掉当前页最后一条时回退一页，避免落在空页
    if (items.value.length === 1 && page.value > 1) {
      page.value -= 1;
    }
    await load();
  } catch (err) {
    error.value = (err as Error).message;
  }
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}

function shortHex(hex: string, head = 8, tail = 8): string {
  return hex.length <= head + tail ? hex : `${hex.slice(0, head)}…${hex.slice(-tail)}`;
}

/** 登录态恢复是异步的，因此要监听它变为已登录后再加载 */
watch(
  () => auth.isLoggedIn,
  (loggedIn) => {
    if (loggedIn && items.value.length === 0) {
      void load();
    }
  },
  { immediate: true },
);
</script>

<template>
  <div class="history-view">
    <header class="head">
      <h1>我的记录</h1>
      <p class="sub">每次加解密都会自动保存，可随时回放当时的完整过程。</p>
    </header>

    <p v-if="!auth.isLoggedIn" class="notice">
      需要登录才能查看记录。<button type="button" class="link" @click="router.push('/login')">去登录</button>
    </p>

    <p v-else-if="error" class="error">{{ error }}</p>

    <template v-else>
      <p v-if="loading" class="loading">加载中…</p>

      <p v-else-if="items.length === 0" class="empty">
        还没有记录。去<button type="button" class="link" @click="router.push('/playground')">生成一次</button>试试。
      </p>

      <div v-else class="list">
        <article v-for="item in items" :key="item.id" class="row">
          <div class="row-main">
            <div class="row-head">
              <span class="tag">{{ item.mode === 'encrypt' ? '加密' : '解密' }}</span>
              <span class="tag alt">AES-{{ item.keyBits }}</span>
              <span class="time">{{ formatTime(item.createdAt) }}</span>
            </div>
            <div class="row-body">
              <span class="kv"><em>输入</em><code>{{ shortHex(item.input) }}</code></span>
              <span class="kv"><em>输出</em><code class="strong">{{ shortHex(item.output) }}</code></span>
            </div>
          </div>

          <div class="row-actions">
            <button type="button" class="btn" @click="replay(item.id)">回放</button>
            <button
              v-if="pendingDelete !== item.id"
              type="button"
              class="btn danger-ghost"
              @click="pendingDelete = item.id"
            >
              删除
            </button>
            <template v-else>
              <button type="button" class="btn danger" @click="confirmDelete(item.id)">确认删除</button>
              <button type="button" class="btn ghost" @click="pendingDelete = null">取消</button>
            </template>
          </div>
        </article>
      </div>

      <div v-if="totalPages > 1" class="pager">
        <button type="button" class="btn" :disabled="page <= 1" @click="gotoPage(page - 1)">上一页</button>
        <span class="page-info">{{ page }} / {{ totalPages }}（共 {{ total }} 条）</span>
        <button type="button" class="btn" :disabled="page >= totalPages" @click="gotoPage(page + 1)">下一页</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.history-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 20px 64px;
}

.head h1 {
  margin: 0 0 8px;
  font-size: 24px;
  color: #111827;
}

.sub {
  margin: 0 0 22px;
  font-size: 13px;
  color: #6b7280;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  flex-wrap: wrap;
}

.row-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.row-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tag {
  padding: 2px 8px;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 600;
}

.tag.alt {
  background: #f3f4f6;
  color: #4b5563;
}

.time {
  font-size: 11px;
  color: #9ca3af;
}

.row-body {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.kv {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
}

.kv em {
  font-style: normal;
  color: #9ca3af;
}

.kv code {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  color: #374151;
}

.kv code.strong {
  color: #4f46e5;
  font-weight: 600;
}

.row-actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 6px 14px;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  background: #ffffff;
  color: #374151;
  font-size: 12px;
  cursor: pointer;
}

.btn:hover:not(:disabled) {
  border-color: #a5b4fc;
  color: #4f46e5;
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn.ghost {
  border-color: transparent;
  color: #9ca3af;
}

.btn.danger {
  border-color: #ef4444;
  background: #ef4444;
  color: #ffffff;
}

.btn.danger-ghost {
  border-color: transparent;
  color: #ef4444;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-top: 22px;
}

.page-info {
  font-size: 12px;
  color: #6b7280;
}

.notice {
  padding: 14px 16px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
  font-size: 13px;
  color: #92400e;
}

.empty {
  padding: 30px;
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
}

.link {
  border: none;
  background: none;
  color: #4f46e5;
  text-decoration: underline;
  cursor: pointer;
  font-size: 13px;
}

.error {
  color: #b91c1c;
  font-size: 13px;
}

.loading {
  color: #6b7280;
  font-size: 13px;
}
</style>