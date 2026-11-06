/**
 * 播放器状态机。
 *
 * 刻意把"当前进度"与"渲染"分离：组件只读 currentStep，
 * 所有交互（播放、单步、跳转、调速、练习冻结）都只改游标。
 * 这样新增交互方式不必改动动画代码。
 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import type { Step, Trace } from '../types/trace';

export type PlayerStatus = 'idle' | 'playing' | 'paused' | 'finished';

/** 基础步进间隔（毫秒），实际间隔为 BASE_INTERVAL / speed */
const BASE_INTERVAL = 1200;

export const SPEEDS = [0.5, 1, 2, 4] as const;
export type Speed = (typeof SPEEDS)[number];

export const usePlayerStore = defineStore('player', () => {
  const trace = ref<Trace | null>(null);
  const cursor = ref(0);
  const status = ref<PlayerStatus>('idle');
  const speed = ref<Speed>(1);
  /** 练习模式下冻结播放控制 */
  const frozen = ref(false);

  let timer: ReturnType<typeof setInterval> | null = null;

  const steps = computed<Step[]>(() => trace.value?.steps ?? []);
  const total = computed(() => steps.value.length);
  const currentStep = computed<Step | null>(() => steps.value[cursor.value] ?? null);
  const progress = computed(() =>
    total.value <= 1 ? 0 : (cursor.value / (total.value - 1)) * 100,
  );
  const isFirst = computed(() => cursor.value <= 0);
  const isLast = computed(() => cursor.value >= total.value - 1);

  /** 当前步骤所属轮次的所有步骤，用于时间轴分组高亮 */
  const currentRoundSteps = computed(() => {
    const step = currentStep.value;
    if (!step) {
      return [];
    }
    return steps.value.filter((s) => s.round === step.round);
  });

  function stopTimer(): void {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  }

  function startTimer(): void {
    stopTimer();
    timer = setInterval(() => {
      if (cursor.value >= total.value - 1) {
        pause();
        status.value = 'finished';
        return;
      }
      cursor.value += 1;
    }, BASE_INTERVAL / speed.value);
  }

  /** 载入新轨迹，重置到起点 */
  function load(next: Trace): void {
    stopTimer();
    trace.value = next;
    cursor.value = 0;
    status.value = 'idle';
    frozen.value = false;
  }

  /** 清空 */
  function clear(): void {
    stopTimer();
    trace.value = null;
    cursor.value = 0;
    status.value = 'idle';
    frozen.value = false;
  }

  function play(): void {
    if (frozen.value || total.value === 0) {
      return;
    }
    if (isLast.value) {
      cursor.value = 0;
    }
    status.value = 'playing';
    startTimer();
  }

  function pause(): void {
    stopTimer();
    if (status.value === 'playing') {
      status.value = 'paused';
    }
  }

  function toggle(): void {
    if (status.value === 'playing') {
      pause();
    } else {
      play();
    }
  }

  function next(): void {
    if (frozen.value) {
      return;
    }
    pause();
    if (cursor.value < total.value - 1) {
      cursor.value += 1;
    }
    if (cursor.value >= total.value - 1) {
      status.value = 'finished';
    }
  }

  function prev(): void {
    if (frozen.value) {
      return;
    }
    pause();
    if (cursor.value > 0) {
      cursor.value -= 1;
    }
  }

  /** 跳到指定轮次的第一步 */
  function jumpToRound(roundNo: number): void {
    const target = steps.value.find((s) => s.round === roundNo);
    if (target) {
      pause();
      cursor.value = target.index;
    }
  }

  /** 跳到指定步骤下标 */
  function jumpTo(index: number): void {
    if (index < 0 || index >= total.value) {
      return;
    }
    pause();
    cursor.value = index;
  }

  function setSpeed(value: Speed): void {
    speed.value = value;
    if (status.value === 'playing') {
      startTimer();
    }
  }

  function reset(): void {
    stopTimer();
    cursor.value = 0;
    status.value = 'idle';
  }

  function setFrozen(value: boolean): void {
    frozen.value = value;
    if (value) {
      pause();
    }
  }

  /** 组件卸载时必须调用，避免幽灵推进与内存泄漏 */
  function dispose(): void {
    stopTimer();
  }

  return {
    trace,
    cursor,
    status,
    speed,
    frozen,
    steps,
    total,
    currentStep,
    progress,
    isFirst,
    isLast,
    currentRoundSteps,
    load,
    clear,
    play,
    pause,
    toggle,
    next,
    prev,
    jumpToRound,
    jumpTo,
    setSpeed,
    reset,
    setFrozen,
    dispose,
  };
});