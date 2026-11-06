import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { usePlayerStore } from '../stores/player';
import type { AesOp, Step, Trace } from '../types/trace';

/** 构造一个包含 n 步的假轨迹（仅用于测状态机，不涉及算法） */
function makeTrace(stepCount: number, rounds = 2): Trace {
  const steps: Step[] = Array.from({ length: stepCount }, (_, i) => ({
    index: i,
    round: Math.min(Math.floor(i / 4), rounds),
    op: 'SubBytes' as AesOp,
    stateBefore: '0'.repeat(32),
    stateAfter: '1'.repeat(32),
    roundKey: null,
    cells: [],
    explain: `第 ${i} 步`,
  }));
  return {
    algorithm: 'AES',
    keyBits: 128,
    mode: 'encrypt',
    rounds,
    input: '0'.repeat(32),
    key: '0'.repeat(32),
    output: '1'.repeat(32),
    keySchedule: [],
    steps,
  };
}

describe('播放器状态机', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('载入后回到起点', () => {
    const player = usePlayerStore();
    player.load(makeTrace(40));
    expect(player.cursor).toBe(0);
    expect(player.total).toBe(40);
    expect(player.status).toBe('idle');
  });

  it('next 递增，到末尾不越界', () => {
    const player = usePlayerStore();
    player.load(makeTrace(3));
    player.next();
    expect(player.cursor).toBe(1);
    player.next();
    player.next();
    player.next();
    expect(player.cursor).toBe(2);
    expect(player.isLast).toBe(true);
  });

  it('prev 递减，到起点不越界', () => {
    const player = usePlayerStore();
    player.load(makeTrace(3));
    player.prev();
    expect(player.cursor).toBe(0);
    player.next();
    player.prev();
    expect(player.cursor).toBe(0);
    expect(player.isFirst).toBe(true);
  });

  it('jumpTo 越界时保持不动', () => {
    const player = usePlayerStore();
    player.load(makeTrace(10));
    player.jumpTo(5);
    expect(player.cursor).toBe(5);
    player.jumpTo(-1);
    expect(player.cursor).toBe(5);
    player.jumpTo(999);
    expect(player.cursor).toBe(5);
  });

  it('jumpToRound 定位到该轮首步', () => {
    const player = usePlayerStore();
    player.load(makeTrace(20, 4));
    player.jumpToRound(2);
    expect(player.cursor).toBe(8);
    expect(player.currentStep?.round).toBe(2);
  });

  it('reset 回到起点', () => {
    const player = usePlayerStore();
    player.load(makeTrace(10));
    player.jumpTo(7);
    player.reset();
    expect(player.cursor).toBe(0);
    expect(player.status).toBe('idle');
  });

  it('冻结时单步失效', () => {
    const player = usePlayerStore();
    player.load(makeTrace(10));
    player.setFrozen(true);
    player.next();
    expect(player.cursor).toBe(0);
    player.setFrozen(false);
    player.next();
    expect(player.cursor).toBe(1);
  });

  it('play 后按速度推进，结束后自动停止', () => {
    vi.useFakeTimers();
    const player = usePlayerStore();
    player.load(makeTrace(3));
    player.play();
    expect(player.status).toBe('playing');

    vi.advanceTimersByTime(1200);
    expect(player.cursor).toBe(1);

    vi.advanceTimersByTime(2400);
    expect(player.cursor).toBe(2);
    expect(player.status).toBe('finished');

    vi.useRealTimers();
    player.dispose();
  });

  it('倒放不会因游标越界而报错', () => {
    vi.useFakeTimers();
    const player = usePlayerStore();
    player.load(makeTrace(3));
    player.play();
    vi.advanceTimersByTime(3600);
    expect(player.cursor).toBe(2);
    player.prev();
    expect(player.cursor).toBe(1);
    vi.useRealTimers();
    player.dispose();
  });

  it('load 新轨迹会停掉旧定时器', () => {
    vi.useFakeTimers();
    const player = usePlayerStore();
    player.load(makeTrace(10));
    player.play();
    player.load(makeTrace(5));
    vi.advanceTimersByTime(5000);
    // 旧定时器若未清理，游标会被推进
    expect(player.cursor).toBe(0);
    vi.useRealTimers();
    player.dispose();
  });

  it('progress 计算正确', () => {
    const player = usePlayerStore();
    player.load(makeTrace(5));
    expect(player.progress).toBe(0);
    player.jumpTo(4);
    expect(player.progress).toBe(100);
  });

  it('dispose 停止定时器', () => {
    vi.useFakeTimers();
    const player = usePlayerStore();
    player.load(makeTrace(10));
    player.play();
    player.dispose();
    vi.advanceTimersByTime(5000);
    expect(player.cursor).toBe(0);
    vi.useRealTimers();
  });

  it('total 为 0 时 play 不启动', () => {
    const player = usePlayerStore();
    expect(player.total).toBe(0);
    player.play();
    expect(player.status).toBe('idle');
    player.dispose();
  });
});