<script setup lang="ts">
/** 步骤时间轴：按轮分组，可点击定位 */
import { computed } from 'vue';
import { usePlayerStore } from '../stores/player';
import { OP_LABELS } from '../types/trace';

const player = usePlayerStore();

interface RoundGroup {
  round: number;
  steps: { index: number; label: string; op: string }[];
}

/** 按轮分组，供时间轴渲染 */
const groups = computed<RoundGroup[]>(() => {
  const map = new Map<number, RoundGroup>();
  for (const step of player.steps) {
    if (!map.has(step.round)) {
      map.set(step.round, { round: step.round, steps: [] });
    }
    map.get(step.round)!.steps.push({
      index: step.index,
      label: OP_LABELS[step.op],
      op: step.op,
    });
  }
  return [...map.values()].sort((a, b) => a.round - b.round);
});

function isActive(index: number): boolean {
  return index === player.cursor;
}
</script>

<template>
  <div class="timeline">
    <div v-for="group in groups" :key="group.round" class="round-group">
      <button
        type="button"
        class="round-label"
        title="跳到该轮第一步"
        @click="player.jumpToRound(group.round)"
      >
        第 {{ group.round }} 轮
      </button>
      <div class="step-list">
        <button
          v-for="step in group.steps"
          :key="step.index"
          type="button"
          class="step-chip"
          :class="{ active: isActive(step.index) }"
          :title="`第 ${step.index + 1} 步：${step.label}`"
          @click="player.jumpTo(step.index)"
        >
          {{ step.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  padding: 12px 4px;
}

.round-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.round-label {
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  background: #f3f4f6;
  color: #4b5563;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.round-label:hover {
  background: #e5e7eb;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.step-chip {
  padding: 4px 8px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #ffffff;
  color: #6b7280;
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.step-chip:hover {
  border-color: #a5b4fc;
  color: #4f46e5;
}

.step-chip.active {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #ffffff;
  font-weight: 600;
}
</style>