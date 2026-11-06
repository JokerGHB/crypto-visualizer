<script setup lang="ts">
/**
 * 4×4 状态矩阵渲染组件。
 *
 * 用 CSS Grid + DOM 而非 Canvas 实现。理由：
 * 1) 单元格需要接收点击事件以查看字节来历，DOM 事件比 Canvas 命中检测简单；
 * 2) 每个单元格的高亮过渡可以直接用 CSS transition；
 * 3) 16 个单元格的 DOM 数量在此规模下不构成性能问题。
 * Canvas 留作后续需要大量位移动画时的优化手段。
 */
import { computed } from 'vue';
import { hexToMatrix, byteColor, type CellChange } from '../types/trace';

interface Props {
  /** 32 位十六进制状态，按列主序展平 */
  hex: string;
  /** 标题 */
  title?: string;
  /** 需要高亮的格子及其变化明细 */
  changes?: CellChange[];
  /** 显示模式：before 显示变化前值，after 显示变化后值 */
  mode?: 'before' | 'after';
  /** 是否显示行列坐标 */
  showAxis?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  changes: () => [],
  mode: 'after',
  showAxis: true,
});

const emit = defineEmits<{
  (
    e: 'cell-click',
    payload: { row: number; col: number; value: string; change?: CellChange },
  ): void;
}>();

const EMPTY = ['--', '--', '--', '--'];

const matrix = computed<string[][]>(() => {
  try {
    return hexToMatrix(props.hex);
  } catch {
    return [EMPTY, EMPTY, EMPTY, EMPTY];
  }
});

/** 按 "row-col" 索引变化明细，避免每次线性查找 */
const changeMap = computed(() => {
  const map = new Map<string, CellChange>();
  for (const c of props.changes) {
    map.set(`${c.row}-${c.col}`, c);
  }
  return map;
});

function cellChange(row: number, col: number): CellChange | undefined {
  return changeMap.value.get(`${row}-${col}`);
}

function isChanged(row: number, col: number): boolean {
  const c = cellChange(row, col);
  return Boolean(c && c.before !== c.after);
}

function displayValue(row: number, col: number): string {
  const c = cellChange(row, col);
  if (props.mode === 'before' && c) {
    return c.before;
  }
  return matrix.value[row][col];
}

function onCellClick(row: number, col: number): void {
  emit('cell-click', {
    row,
    col,
    value: displayValue(row, col),
    change: cellChange(row, col),
  });
}

function tooltip(row: number, col: number): string {
  const c = cellChange(row, col);
  if (c) {
    const aux = c.aux ? ` · ${c.aux}` : '';
    return `r${row}c${col}: ${c.before} → ${c.after}${aux}`;
  }
  return `r${row}c${col}: ${displayValue(row, col)}`;
}

/** 变化格用实心字节色，静态格用淡色底，便于一眼看出改动位置 */
function cellStyle(row: number, col: number): Record<string, string> {
  const value = displayValue(row, col);
  if (value === '--') {
    return {};
  }
  const color = byteColor(value);
  if (isChanged(row, col)) {
    return {
      backgroundColor: color,
      color: '#ffffff',
      boxShadow: `inset 0 0 0 2px ${color}, 0 2px 10px rgba(15, 23, 42, 0.18)`,
    };
  }
  return {
    backgroundColor: `color-mix(in srgb, ${color} 10%, #ffffff)`,
    color: '#1f2937',
    boxShadow: 'inset 0 0 0 1px rgba(148, 163, 184, 0.35)',
  };
}
</script>

<template>
  <div class="state-matrix">
    <div v-if="title" class="matrix-title">{{ title }}</div>

    <div class="matrix-grid" :class="{ 'with-axis': showAxis }">
      <template v-if="showAxis">
        <span class="corner" />
        <span v-for="c in 4" :key="`hc${c}`" class="head">{{ `c${c - 1}` }}</span>
      </template>

      <template v-for="r in 4" :key="`r${r}`">
        <span v-if="showAxis" class="head row-head">{{ `r${r - 1}` }}</span>
        <button
          v-for="c in 4"
          :key="`${r}-${c}`"
          type="button"
          class="cell"
          :class="{ changed: isChanged(r - 1, c - 1) }"
          :style="cellStyle(r - 1, c - 1)"
          :title="tooltip(r - 1, c - 1)"
          @click="onCellClick(r - 1, c - 1)"
        >
          {{ displayValue(r - 1, c - 1) }}
        </button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.state-matrix {
  display: inline-flex;
  flex-direction: column;
  gap: 8px;
}

.matrix-title {
  font-size: 13px;
  font-weight: 600;
  color: #4b5563;
}

.matrix-grid {
  display: grid;
  gap: 6px;
}

.matrix-grid.with-axis {
  grid-template-columns: 20px repeat(4, 52px);
  grid-template-rows: 16px repeat(4, 52px);
}

.matrix-grid:not(.with-axis) {
  grid-template-columns: repeat(4, 52px);
  grid-template-rows: repeat(4, 52px);
}

.corner {
  grid-column: 1;
  grid-row: 1;
}

.head {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #9ca3af;
  user-select: none;
}

.row-head {
  grid-column: 1;
}

.cell {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 0.25s ease,
    box-shadow 0.25s ease,
    transform 0.12s ease;
}

.cell:hover {
  transform: translateY(-1px);
}

.cell.changed {
  animation: cell-pop 0.3s ease;
}

@keyframes cell-pop {
  0% {
    transform: scale(0.9);
  }
  60% {
    transform: scale(1.05);
  }
  100% {
    transform: scale(1);
  }
}
</style>