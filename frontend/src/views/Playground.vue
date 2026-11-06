<script setup lang="ts">
/**
 * 主工作区：参数配置 + 播放控制 + 双矩阵对照 + 时间轴 + AI 辅导。
 *
 * 所有可视化数据来自后端返回的 Trace，前端不做任何算法计算。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AiTutorPanel from '../components/AiTutorPanel.vue';
import KeyScheduleView from '../components/KeyScheduleView.vue';
import PlayerControls from '../components/PlayerControls.vue';
import StateMatrix from '../components/StateMatrix.vue';
import StepTimeline from '../components/StepTimeline.vue';
import { computeAes } from '../api/crypto';
import { getSessionDetail } from '../api/history';
import { usePlayerStore } from '../stores/player';
import { OP_LABELS, type AesKeyBits, type AesMode, type CellChange } from '../types/trace';

const player = usePlayerStore();
const route = useRoute();
const router = useRouter();

const plaintext = ref('3243f6a8885a308d313198a2e0370734');
const keyInput = ref('2b7e151628aed2a6abf7158809cf4f3c');
const keyBits = ref<AesKeyBits>(128);
const mode = ref<AesMode>('encrypt');

/** 文本模式输入（自动转十六进制） */
const plaintextText = ref('');
const keyText = ref('');
const useTextInput = ref(false);

const loading = ref(false);
const error = ref<string | null>(null);

/** 回放模式：从历史记录载入，不允许改参数重新计算 */
const replayMode = ref(false);

/** 单元格点击后展示的字节来历 */
const cellDetail = ref<{ row: number; col: number; value: string; change?: CellChange } | null>(null);

const KEY_HEX_LEN: Record<AesKeyBits, number> = { 128: 32, 192: 48, 256: 64 };

const current = computed(() => player.currentStep);
const trace = computed(() => player.trace);

const changes = computed<CellChange[]>(() => current.value?.cells ?? []);

/** 密钥输入长度是否匹配 */
const keyLengthOk = computed(
  () => keyInput.value.trim().length === KEY_HEX_LEN[keyBits.value],
);

const canCompute = computed(
  () =>
    !loading.value &&
    /^[0-9a-fA-F]{32}$/.test(plaintext.value.trim()) &&
    keyLengthOk.value,
);

/** 切换密钥长度时给出对应长度的占位提示 */
watch(keyBits, (bits) => {
  if (keyInput.value.length !== KEY_HEX_LEN[bits]) {
    error.value = `AES-${bits} 需要 ${KEY_HEX_LEN[bits]} 位十六进制密钥`;
  } else {
    error.value = null;
  }
});

/** 切换加密/解密时，把上一次的输出自动填成新输入，便于验证互逆 */
watch(mode, (next, prev) => {
  if (replayMode.value || !trace.value || next === prev) {
    return;
  }
  // 从加密切到解密：把密文作为输入；反之把明文作为输入
  plaintext.value = trace.value.output;
});
function textToHex(text: string): string {
  return Array.from(new TextEncoder().encode(text))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

watch(plaintextText, (text) => {
  if (!useTextInput.value) {
    return;
  }
  const hex = textToHex(text);
  plaintext.value = hex.padEnd(32, '0').slice(0, 32);
});

watch(keyText, (text) => {
  if (!useTextInput.value) {
    return;
  }
  const hex = textToHex(text);
  const len = KEY_HEX_LEN[keyBits.value];
  keyInput.value = hex.padEnd(len, '0').slice(0, len);
});

async function compute(): Promise<void> {
  if (!canCompute.value) {
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const result = await computeAes({
      input: plaintext.value.trim().toLowerCase(),
      key: keyInput.value.trim().toLowerCase(),
      keyBits: keyBits.value,
      mode: mode.value,
    });
    player.load(result);
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    loading.value = false;
  }
}

/** 从历史记录载入轨迹 */
async function loadFromHistory(id: number): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const detail = await getSessionDetail(id);
    player.load(detail.trace);
    plaintext.value = detail.trace.input;
    keyInput.value = detail.trace.key;
    keyBits.value = detail.trace.keyBits;
    mode.value = detail.trace.mode;
    replayMode.value = true;
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    loading.value = false;
  }
}

function exitReplay(): void {
  replayMode.value = false;
  router.replace({ path: '/playground' });
}

function onCellClick(payload: { row: number; col: number; value: string; change?: CellChange }): void {
  cellDetail.value = payload;
}

/** 快捷键：左右方向键单步 */
function onKeyup(event: KeyboardEvent): void {
  const target = event.target as HTMLElement;
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
    return;
  }
  if (event.key === 'ArrowRight') {
    player.next();
  } else if (event.key === 'ArrowLeft') {
    player.prev();
  } else if (event.key === ' ') {
    event.preventDefault();
    player.toggle();
  }
}

onMounted(async () => {
  window.addEventListener('keyup', onKeyup);
  const sessionQuery = route.query.session;
  if (typeof sessionQuery === 'string') {
    await loadFromHistory(Number(sessionQuery));
  } else {
    await compute();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('keyup', onKeyup);
  // 必须清理定时器，否则离开页面后仍会推进游标
  player.dispose();
});
</script>

<template>
  <div class="playground">
    <!-- 左栏：参数与密钥扩展 -->
    <section class="sidebar">
      <div class="card">
        <h3 class="card-title">参数配置</h3>

        <label class="field">
          <span>算法</span>
          <select v-model.number="keyBits" :disabled="replayMode">
            <option :value="128">AES-128（10 轮）</option>
            <option :value="192">AES-192（12 轮）</option>
            <option :value="256">AES-256（14 轮）</option>
          </select>
        </label>

        <label class="field">
          <span>模式</span>
          <select v-model="mode" :disabled="replayMode">
            <option value="encrypt">加密</option>
            <option value="decrypt">解密</option>
          </select>
        </label>

        <label class="toggle">
          <input v-model="useTextInput" type="checkbox" :disabled="replayMode" />
          <span>用文本输入（自动转十六进制）</span>
        </label>

        <template v-if="useTextInput">
          <label class="field column">
            <span>明文 / 密文文本（取前 16 字节）</span>
            <input v-model="plaintextText" type="text" :disabled="replayMode" placeholder="例如 hello aes world!" />
          </label>
          <label class="field column">
            <span>密钥文本</span>
            <input v-model="keyText" type="text" :disabled="replayMode" placeholder="例如 my secret key" />
          </label>
        </template>

        <label class="field column">
          <span>
            输入（32 位十六进制）
            <em class="mode-hint">{{ mode === 'decrypt' ? '密文' : '明文' }}</em>
          </span>
          <input
            v-model="plaintext"
            type="text"
            maxlength="32"
            spellcheck="false"
            :disabled="replayMode"
            class="mono"
            :placeholder="mode === 'decrypt' ? '粘贴密文，或先加密再切换过来' : '32 位十六进制明文'"
          />
        </label>

        <label class="field column">
          <span>
            密钥（{{ KEY_HEX_LEN[keyBits] }} 位十六进制）
            <em v-if="!keyLengthOk" class="warn-inline">长度不符</em>
          </span>
          <input
            v-model="keyInput"
            type="text"
            :maxlength="KEY_HEX_LEN[keyBits]"
            spellcheck="false"
            :disabled="replayMode"
            class="mono"
          />
        </label>

        <div class="actions">
          <button type="button" class="btn primary" :disabled="!canCompute || replayMode" @click="compute">
            {{ loading ? '计算中…' : '生成轨迹' }}
          </button>
          <button v-if="replayMode" type="button" class="btn ghost" @click="exitReplay">
            退出回放
          </button>
        </div>

        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="replayMode" class="note">当前为历史回放，参数已锁定。</p>
      </div>

      <div class="card">
        <h3 class="card-title">结果</h3>
        <div class="kv">
          <span class="k">输入</span>
          <code class="v">{{ trace?.input ?? '—' }}</code>
        </div>
        <div class="kv">
          <span class="k">{{ trace?.mode === 'decrypt' ? '明文' : '密文' }}</span>
          <code class="v strong">{{ trace?.output ?? '—' }}</code>
        </div>
        <div class="kv">
          <span class="k">轮数</span>
          <span class="v">{{ trace?.rounds ?? '—' }}</span>
        </div>
        <div class="kv">
          <span class="k">总步数</span>
          <span class="v">{{ player.total }}</span>
        </div>
      </div>

      <div v-if="trace" class="card">
        <KeyScheduleView
          :rounds="trace.keySchedule"
          :active-round="current?.round ?? -1"
          @select-round="player.jumpToRound"
        />
      </div>
    </section>

    <!-- 中栏：矩阵与播放 -->
    <section class="main">
      <div class="card">
        <div class="step-head">
          <h3 class="card-title">
            第 {{ current?.round ?? 0 }} 轮 ·
            {{ current ? OP_LABELS[current.op] : '等待载入' }}
          </h3>
          <span v-if="current" class="step-index">第 {{ current.index + 1 }} 步</span>
        </div>

        <p v-if="current" class="explain">{{ current.explain }}</p>

        <div v-if="current" class="matrices">
          <StateMatrix
            :hex="current.stateBefore"
            title="操作前"
            mode="before"
            :changes="changes"
            @cell-click="onCellClick"
          />
          <div class="arrow">→</div>
          <StateMatrix
            :hex="current.stateAfter"
            title="操作后"
            mode="after"
            :changes="changes"
            @cell-click="onCellClick"
          />
        </div>

        <div v-if="current?.roundKey" class="roundkey">
          <span class="rk-label">本轮轮密钥</span>
          <code class="rk-value">{{ current.roundKey }}</code>
        </div>
      </div>

      <PlayerControls />

      <div v-if="player.total > 0" class="card">
        <h3 class="card-title">步骤时间轴</h3>
        <StepTimeline />
      </div>

      <div v-if="cellDetail" class="card cell-detail">
        <div class="cd-head">
          <h4>字节来历 · r{{ cellDetail.row }}c{{ cellDetail.col }}</h4>
          <button type="button" class="link-btn" @click="cellDetail = null">关闭</button>
        </div>
        <template v-if="cellDetail.change">
          <p class="cd-line">
            <span class="cd-k">变化</span>
            <code>{{ cellDetail.change.before }}</code>
            →
            <code>{{ cellDetail.change.after }}</code>
          </p>
          <p v-if="cellDetail.change.aux" class="cd-line">
            <span class="cd-k">依据</span>
            <code>{{ cellDetail.change.aux }}</code>
          </p>
        </template>
        <p v-else class="cd-line">
          <span class="cd-k">当前值</span>
          <code>{{ cellDetail.value }}</code>
          <span class="muted">（该步未改变此字节）</span>
        </p>
      </div>
    </section>

    <!-- 右栏：AI 辅导 -->
    <section class="aside">
      <AiTutorPanel
        :step="current"
        :key-bits="trace?.keyBits ?? 128"
        :mode="trace?.mode ?? 'encrypt'"
        :total-steps="player.total"
      />
    </section>
  </div>
</template>

<style scoped>
.playground {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 320px;
  gap: 16px;
  padding: 16px;
  align-items: start;
}

@media (max-width: 1280px) {
  .playground {
    grid-template-columns: 280px minmax(0, 1fr);
  }
  .aside {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .playground {
    grid-template-columns: 1fr;
  }
}

.sidebar,
.main {
  display: flex;
  flex-direction: column;
  gap: 14px;
  /* min-width: 0 防止网格子项被内部等宽内容撑破 */
  min-width: 0;
}

.sidebar > .card,
.main > .card {
  min-width: 0;
}

/* 仅密钥扩展卡片需要裁剪滚动，其他卡片保持可见溢出（如时间轴横向滚动） */
.sidebar > .card:last-child {
  overflow: hidden;
}

.aside {
  position: sticky;
  top: 16px;
  height: calc(100vh - 32px);
}

.card {
  padding: 14px 16px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
}

.card-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #6b7280;
}

.field.column {
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
}

.field select,
.field input {
  padding: 6px 9px;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  font-size: 12.5px;
  background: #ffffff;
  color: #1f2937;
  outline: none;
}

.field select:focus,
.field input:focus {
  border-color: #a5b4fc;
}

.field input.mono {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 11.5px;
}

.field input:disabled,
.field select:disabled {
  background: #f9fafb;
  color: #9ca3af;
}

.toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.btn {
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 12.5px;
  cursor: pointer;
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #374151;
}

.btn.primary {
  flex: 1;
  background: #4f46e5;
  border-color: #4f46e5;
  color: #ffffff;
}

.btn.primary:disabled {
  background: #c7d2fe;
  border-color: #c7d2fe;
  cursor: not-allowed;
}

.btn.ghost {
  background: transparent;
}

.error {
  margin: 8px 0 0;
  font-size: 11.5px;
  color: #b91c1c;
  line-height: 1.6;
}

.note {
  margin: 8px 0 0;
  font-size: 11.5px;
  color: #b45309;
}

.warn-inline {
  font-style: normal;
  color: #b91c1c;
  font-size: 11px;
}

.mode-hint {
  font-style: normal;
  margin-left: 6px;
  padding: 1px 6px;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 4px;
  font-size: 10.5px;
}

.kv {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 9px;
}

.kv .k {
  font-size: 11px;
  color: #9ca3af;
}

.kv .v {
  font-size: 11.5px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  color: #374151;
  word-break: break-all;
}

.kv .v.strong {
  color: #4f46e5;
  font-weight: 600;
}

.step-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.step-index {
  font-size: 11.5px;
  color: #9ca3af;
}

.explain {
  margin: 0 0 16px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #4b5563;
}

.matrices {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
  justify-content: center;
  padding: 8px 0;
}

.arrow {
  font-size: 22px;
  color: #d1d5db;
  user-select: none;
}

.roundkey {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #e5e7eb;
}

.rk-label {
  font-size: 11.5px;
  color: #9ca3af;
}

.rk-value {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 11.5px;
  color: #b45309;
  word-break: break-all;
}

.cell-detail {
  border-color: #c7d2fe;
  background: #f8faff;
}

.cd-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cd-head h4 {
  margin: 0 0 8px;
  font-size: 12.5px;
  color: #4338ca;
}

.link-btn {
  border: none;
  background: none;
  color: #9ca3af;
  font-size: 11.5px;
  cursor: pointer;
}

.cd-line {
  margin: 5px 0;
  font-size: 12px;
  color: #4b5563;
  display: flex;
  align-items: center;
  gap: 8px;
}

.cd-k {
  display: inline-block;
  width: 42px;
  color: #9ca3af;
  font-size: 11px;
}

.cd-line code {
  padding: 1px 6px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  font-family: 'Consolas', monospace;
  font-size: 11.5px;
  color: #1f2937;
}

.muted {
  color: #9ca3af;
  font-size: 11px;
}
</style>