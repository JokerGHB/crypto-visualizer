<script setup lang="ts">
/** 播放控制条：播放/暂停、单步、跳轮、调速、重置 */
import { computed } from 'vue';
import { SPEEDS, usePlayerStore, type Speed } from '../stores/player';

const player = usePlayerStore();

const statusText = computed(() => {
  switch (player.status) {
    case 'playing':
      return '播放中';
    case 'paused':
      return '已暂停';
    case 'finished':
      return '已结束';
    default:
      return '未开始';
  }
});

const playLabel = computed(() =>
  player.status === 'playing' ? '暂停' : '播放',
);

function onSpeedChange(event: Event): void {
  const value = Number((event.target as HTMLSelectElement).value) as Speed;
  player.setSpeed(value);
}

function onJumpRound(event: Event): void {
  const value = Number((event.target as HTMLSelectElement).value);
  if (!Number.isNaN(value)) {
    player.jumpToRound(value);
  }
}

const roundOptions = computed(() => {
  const rounds = player.trace?.rounds ?? 0;
  return Array.from({ length: rounds + 1 }, (_, i) => i);
});
</script>

<template>
  <div class="controls" :class="{ frozen: player.frozen }">
    <div class="row">
      <button type="button" class="btn primary" :disabled="player.frozen" @click="player.toggle()">
        {{ playLabel }}
      </button>
      <button type="button" class="btn" :disabled="player.frozen || player.isFirst" @click="player.prev()">
        上一步
      </button>
      <button type="button" class="btn" :disabled="player.frozen || player.isLast" @click="player.next()">
        下一步
      </button>
      <button type="button" class="btn ghost" :disabled="player.frozen" @click="player.reset()">
        重置
      </button>
    </div>

    <div class="row">
      <label class="field">
        <span>速度</span>
        <select :value="player.speed" :disabled="player.frozen" @change="onSpeedChange">
          <option v-for="s in SPEEDS" :key="s" :value="s">{{ s }}×</option>
        </select>
      </label>

      <label class="field">
        <span>跳到轮次</span>
        <select :disabled="player.frozen || !player.trace" @change="onJumpRound">
          <option value="">选择</option>
          <option v-for="r in roundOptions" :key="r" :value="r">第 {{ r }} 轮</option>
        </select>
      </label>
    </div>

    <div class="status">
      <span class="step-badge">
        第 {{ player.total === 0 ? 0 : player.cursor + 1 }} / {{ player.total }} 步
      </span>
      <span class="state-label">{{ statusText }}</span>
      <span v-if="player.frozen" class="frozen-tip">练习中已冻结</span>
    </div>

    <div class="progress">
      <div class="progress-bar" :style="{ width: `${player.progress}%` }" />
    </div>
  </div>
</template>

<style scoped>
.controls {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.controls.frozen {
  opacity: 0.75;
}

.row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.btn {
  padding: 7px 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn:hover:not(:disabled) {
  border-color: #6366f1;
  color: #4f46e5;
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn.primary {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #ffffff;
  min-width: 76px;
}

.btn.primary:hover:not(:disabled) {
  background: #4338ca;
  color: #ffffff;
}

.btn.ghost {
  background: transparent;
  border-color: transparent;
  color: #6b7280;
}

.field {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7280;
}

.field select {
  padding: 5px 8px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 12px;
  background: #ffffff;
  cursor: pointer;
}

.status {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #6b7280;
}

.step-badge {
  padding: 3px 10px;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 999px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.frozen-tip {
  color: #b45309;
}

.progress {
  height: 4px;
  background: #f3f4f6;
  border-radius: 999px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #a855f7);
  transition: width 0.2s ease;
}
</style>