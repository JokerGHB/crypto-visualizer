<script setup lang="ts">
/**
 * 密钥扩展可视化。
 *
 * 展示各轮轮密钥的 4 个字，以及 RotWord / SubWord / Rcon / XOR 四步生成明细。
 * 因侧栏空间有限且轮次较多（11~15 组），默认只展开当前播放轮，
 * 其余折叠为一行，点击可切换。全部展开时需要用户主动操作。
 */
import { computed, ref, watch } from 'vue';
import type { KeyScheduleRound } from '../types/trace';

interface Props {
  rounds: KeyScheduleRound[];
  /** 当前播放所在轮次，用于高亮与自动展开 */
  activeRound?: number;
}

const props = withDefaults(defineProps<Props>(), { activeRound: -1 });

const emit = defineEmits<{ (e: 'select-round', round: number): void }>();

/** 用户手动展开的轮次集合；播放时自动跟随当前轮 */
const manualOpen = ref<Set<number>>(new Set());
const expanded = ref<Set<number>>(new Set());

/** 有生成明细的轮次（并非每轮都有，取决于 nk 与 4 的对齐情况） */
const detailRounds = computed(() =>
  props.rounds.filter((r) => r.detail).map((r) => r.round),
);

/** 跟随播放进度自动展开当前轮，便于对照左侧动画 */
watch(
  () => props.activeRound,
  (roundNo) => {
    if (roundNo >= 0) {
      expanded.value = new Set([roundNo, ...manualOpen.value]);
    }
  },
  { immediate: true },
);

function toggle(roundNo: number): void {
  const next = new Set(expanded.value);
  if (next.has(roundNo)) {
    next.delete(roundNo);
    manualOpen.value.delete(roundNo);
  } else {
    next.add(roundNo);
    manualOpen.value.add(roundNo);
  }
  expanded.value = next;
  emit('select-round', roundNo);
}

function isOpen(roundNo: number): boolean {
  return expanded.value.has(roundNo);
}

function wordBytes(word: string): string[] {
  return [
    word.slice(0, 2),
    word.slice(2, 4),
    word.slice(4, 6),
    word.slice(6, 8),
  ];
}
</script>

<template>
  <div class="key-schedule">
    <header class="head">
      <h3>密钥扩展</h3>
      <span class="meta">
        {{ rounds.length }} 组轮密钥 · 含明细：{{ detailRounds.join('、') || '无' }}
      </span>
    </header>

    <div class="rounds">
      <div
        v-for="item in rounds"
        :key="item.round"
        class="round-card"
        :class="{ active: item.round === activeRound, open: isOpen(item.round) }"
      >
        <button type="button" class="round-head" @click="toggle(item.round)">
          <span class="badge">W[{{ item.round * 4 }}..{{ item.round * 4 + 3 }}]</span>
          <span class="round-no">第 {{ item.round }} 轮</span>
          <span class="chev">{{ isOpen(item.round) ? '−' : '+' }}</span>
        </button>

        <!-- 折叠时也显示轮密钥字，保证信息可见 -->
        <div class="words">
          <div v-for="(word, wi) in item.words" :key="wi" class="word">
            <span v-for="(b, bi) in wordBytes(word)" :key="bi" class="byte">{{ b }}</span>
          </div>
        </div>

        <div v-if="item.detail && isOpen(item.round)" class="detail">
          <div class="detail-row">
            <span class="label">RotWord</span>
            <span class="bytes">
              <span v-for="(b, i) in wordBytes(item.detail.rotWord)" :key="i" class="byte small">{{ b }}</span>
            </span>
          </div>
          <div class="detail-row">
            <span class="label">SubWord</span>
            <span class="bytes">
              <span v-for="(b, i) in wordBytes(item.detail.subWord)" :key="i" class="byte small">{{ b }}</span>
            </span>
          </div>
          <div class="detail-row">
            <span class="label">⊕ Rcon</span>
            <span class="bytes">
              <span v-for="(b, i) in wordBytes(item.detail.rcon)" :key="i" class="byte small">{{ b }}</span>
            </span>
          </div>
          <div class="detail-row result">
            <span class="label">= 临时字</span>
            <span class="bytes">
              <span v-for="(b, i) in wordBytes(item.detail.xor)" :key="i" class="byte small strong">{{ b }}</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.key-schedule {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.meta {
  font-size: 10.5px;
  line-height: 1.5;
  color: #9ca3af;
}

.rounds {
  display: flex;
  flex-direction: column;
  gap: 6px;
  /* 限制高度并允许内部滚动，避免把侧栏撑到数千像素 */
  max-height: 420px;
  overflow-y: auto;
  padding-right: 3px;
}

.round-card {
  padding: 7px 8px;
  border: 1px solid #e5e7eb;
  border-radius: 9px;
  background: #ffffff;
  min-width: 0;
  transition: border-color 0.15s ease;
}

.round-card.active {
  border-color: #4f46e5;
  box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.1);
}

.round-head {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 0 0 5px;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
}

.badge {
  padding: 1px 6px;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 4px;
  font-size: 10px;
  font-family: 'Consolas', monospace;
}

.round-no {
  font-size: 10.5px;
  color: #9ca3af;
}

.chev {
  margin-left: auto;
  font-size: 13px;
  color: #9ca3af;
  line-height: 1;
}

.round-card.open .chev {
  color: #4f46e5;
}

.words {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
}

.word {
  display: flex;
  gap: 1px;
  padding: 2px;
  background: #f9fafb;
  border-radius: 4px;
}

.byte {
  display: inline-block;
  min-width: 15px;
  padding: 1px;
  text-align: center;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 9.5px;
  color: #374151;
  background: #ffffff;
  border-radius: 3px;
}

.byte.small {
  font-size: 9px;
  min-width: 14px;
}

.byte.strong {
  background: #fef3c7;
  color: #78350f;
  font-weight: 700;
}

.detail {
  margin-top: 8px;
  padding-top: 7px;
  border-top: 1px dashed #e5e7eb;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.label {
  width: 56px;
  flex-shrink: 0;
  font-size: 9.5px;
  color: #9ca3af;
}

.bytes {
  display: flex;
  gap: 1px;
}

.detail-row.result .label {
  color: #b45309;
  font-weight: 600;
}
</style>