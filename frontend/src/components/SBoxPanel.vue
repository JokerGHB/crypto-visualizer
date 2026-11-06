<script setup lang="ts">
/** S 盒 / 逆 S 盒 16×16 表格，支持搜索、悬停提示与点击反查 */
import { computed, onMounted, ref } from 'vue';
import { fetchSBox } from '../api/crypto';

const inverse = ref(false);
const table = ref<number[][]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const query = ref('');

/** 高亮：点击某格后记录其坐标，同时用搜索词反查 */
const picked = ref<number | null>(null);

const rowHeads = '0123456789abcdef'.split('');
const colHeads = '0123456789abcdef'.split('');

const HEX_RE = /^[0-9a-f]{1,2}$/i;

/** 搜索结果：返回命中的坐标集合 */
const matches = computed(() => {
  const raw = query.value.trim().replace(/^0x/i, '');
  const set = new Set<string>();
  if (!HEX_RE.test(raw)) {
    return set;
  }
  const target = parseInt(raw, 16);
  for (let r = 0; r < 16; r += 1) {
    for (let c = 0; c < 16; c += 1) {
      if (table.value[r]?.[c] === target) {
        set.add(`${r}-${c}`);
      }
    }
  }
  return set;
});

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const result = await fetchSBox(inverse.value);
    table.value = result.table;
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    loading.value = false;
  }
}

function toggleInverse(): void {
  inverse.value = !inverse.value;
  picked.value = null;
  load();
}

function hex2(value: number): string {
  return value.toString(16).padStart(2, '0');
}

function onCellClick(value: number): void {
  picked.value = value;
  query.value = hex2(value);
}

onMounted(load);
</script>

<template>
  <div class="sbox-panel">
    <header class="panel-head">
      <h2>S 盒 {{ inverse ? '（逆 S 盒）' : '' }}</h2>
      <div class="actions">
        <input
          v-model="query"
          class="search"
          type="text"
          maxlength="4"
          placeholder="输入字节反查，如 d4"
        />
        <button type="button" class="btn" @click="toggleInverse">
          切换到{{ inverse ? 'S 盒' : '逆 S 盒' }}
        </button>
      </div>
    </header>

    <p class="hint">
      行表示字节的高 4 位，列表示低 4 位。例如 <code>sbox[0x19]</code> = 第 1 行第 9 列 =
      <code>d4</code>。点击任意格可反查该值出现的位置。
    </p>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="loading" class="loading">加载中…</p>

    <div v-else class="table-wrap">
      <table class="sbox-table">
        <thead>
          <tr>
            <th class="corner">↑↓ / →</th>
            <th v-for="c in colHeads" :key="`ch${c}`">{{ c }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, r) in table" :key="`r${r}`">
            <th class="row-head">{{ rowHeads[r] }}</th>
            <td
              v-for="(value, c) in row"
              :key="`${r}-${c}`"
              :class="{
                match: matches.has(`${r}-${c}`),
                picked: picked === value,
              }"
              :title="`sbox[${rowHeads[r]}${colHeads[c]}] = ${hex2(value)}`"
              @click="onCellClick(value)"
            >
              {{ hex2(value) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="query && matches.size === 0 && !loading" class="hint warn">
      未找到值为 {{ query }} 的格子，请检查输入。
    </p>
  </div>
</template>

<style scoped>
.sbox-panel {
  padding: 20px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.panel-head h2 {
  margin: 0;
  font-size: 17px;
  color: #111827;
}

.actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search {
  padding: 6px 10px;
  width: 180px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
}

.btn {
  padding: 6px 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  font-size: 13px;
  cursor: pointer;
}

.btn:hover {
  border-color: #6366f1;
  color: #4f46e5;
}

.hint {
  margin: 12px 0 16px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #6b7280;
}

.hint code {
  padding: 1px 5px;
  background: #f3f4f6;
  border-radius: 4px;
  font-family: 'Consolas', monospace;
  color: #4b5563;
}

.hint.warn {
  color: #b45309;
}

.error {
  color: #b91c1c;
  font-size: 13px;
}

.loading {
  color: #6b7280;
  font-size: 13px;
}

.table-wrap {
  overflow-x: auto;
}

.sbox-table {
  border-collapse: collapse;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
}

.sbox-table th {
  padding: 5px 7px;
  color: #6b7280;
  font-weight: 600;
  background: #f9fafb;
  font-size: 11px;
}

.sbox-table .corner {
  font-size: 10px;
  color: #9ca3af;
}

.sbox-table .row-head {
  text-align: center;
}

.sbox-table td {
  padding: 5px 7px;
  text-align: center;
  border: 1px solid #f1f5f9;
  color: #374151;
  cursor: pointer;
  transition: background-color 0.12s ease;
}

.sbox-table td:hover {
  background: #eef2ff;
}

.sbox-table td.match {
  background: #fde68a;
  color: #78350f;
  font-weight: 700;
}

.sbox-table td.picked {
  background: #4f46e5;
  color: #ffffff;
  font-weight: 700;
}
</style>