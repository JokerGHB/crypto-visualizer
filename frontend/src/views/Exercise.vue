<script setup lang="ts">
/**
 * 练习模式页。
 *
 * 答错后可跳转到对应动画步骤，形成「练习 → 纠错 → 回看」闭环。
 */
import { computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import StateMatrix from '../components/StateMatrix.vue';
import { generateExercise, submitAnswer } from '../api/exercise';
import { useAuthStore } from '../stores/auth';
import type { Exercise, ExerciseResult } from '../types/trace';

const router = useRouter();
const auth = useAuthStore();

const types = [
  { type: 'step_identify', label: '步骤识别' },
  { type: 'cell_result', label: '结果填写' },
  { type: 'key_param', label: '参数调试' },
];

const activeType = ref('step_identify');
const exercise = ref<Exercise | null>(null);
const answer = ref('');
const result = ref<ExerciseResult | null>(null);
const loading = ref(false);
const submitting = ref(false);
const error = ref<string | null>(null);

/** 步骤识别题的选项 */
const options = computed<string[]>(() => {
  const raw = exercise.value?.snapshot?.options;
  return Array.isArray(raw) ? (raw as string[]) : [];
});

/** 题面展示用的前后状态矩阵（仅部分题型有） */
const stateBefore = computed<string | null>(() => {
  const raw = exercise.value?.snapshot?.stateBefore;
  return typeof raw === 'string' ? raw : null;
});

const stateAfter = computed<string | null>(() => {
  const raw = exercise.value?.snapshot?.stateAfter;
  return typeof raw === 'string' ? raw : null;
});

const isStepType = computed(() => activeType.value === 'step_identify');

async function next(): Promise<void> {
  if (!auth.isLoggedIn) {
    error.value = '练习模式需要登录后使用';
    return;
  }
  loading.value = true;
  error.value = null;
  result.value = null;
  answer.value = '';
  try {
    exercise.value = await generateExercise(activeType.value);
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    loading.value = false;
  }
}

function pickOption(option: string): void {
  answer.value = option;
}

async function check(): Promise<void> {
  if (!exercise.value || !answer.value.trim()) {
    return;
  }
  submitting.value = true;
  error.value = null;
  try {
    result.value = await submitAnswer(exercise.value.exerciseId, answer.value.trim());
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    submitting.value = false;
  }
}

/** 跳到动画中的对应步骤复盘 */
function gotoStep(): void {
  if (result.value?.stepIndex != null) {
    router.push({ path: '/playground', query: { focus: String(result.value.stepIndex) } });
  }
}

function switchType(type: string): void {
  activeType.value = type;
  exercise.value = null;
  result.value = null;
  answer.value = '';
  void next();
}

/** 登录态异步恢复，等就绪后再出题，避免首屏因未登录而空白 */
watch(
  () => auth.isLoggedIn,
  (loggedIn) => {
    if (loggedIn && !exercise.value) {
      void next();
    }
  },
  { immediate: true },
);
</script>

<template>
  <div class="exercise-view">
    <header class="head">
      <h1>练习模式</h1>
      <p class="sub">题目由后端依据真实轨迹生成，答案不出现在前端；答错可跳回动画复盘。</p>
    </header>

    <div class="type-tabs">
      <button
        v-for="t in types"
        :key="t.type"
        type="button"
        class="tab"
        :class="{ active: activeType === t.type }"
        @click="switchType(t.type)"
      >
        {{ t.label }}
      </button>
    </div>

    <p v-if="!auth.isLoggedIn" class="notice">
      需要登录才能练习。<button type="button" class="link" @click="router.push('/login')">去登录</button>
    </p>

    <p v-else-if="error" class="error">{{ error }}</p>

    <div v-else-if="exercise" class="card">
      <p class="prompt">{{ exercise.prompt }}</p>

      <div v-if="stateBefore || stateAfter" class="matrices">
        <StateMatrix v-if="stateBefore" :hex="stateBefore" title="状态 A" mode="after" />
        <span v-if="stateBefore && stateAfter" class="arrow">→</span>
        <StateMatrix v-if="stateAfter" :hex="stateAfter" title="状态 B" mode="after" />
      </div>

      <!-- 步骤识别：四选一 -->
      <div v-if="isStepType" class="options">
        <button
          v-for="opt in options"
          :key="opt"
          type="button"
          class="option"
          :class="{
            picked: answer === opt,
            correct: result && opt === result.expected,
            wrong: result && answer === opt && !result.isCorrect,
          }"
          :disabled="Boolean(result)"
          @click="pickOption(opt)"
        >
          {{ opt }}
        </button>
      </div>

      <!-- 其余题型：填空 -->
      <div v-else class="fill">
        <input
          v-model="answer"
          type="text"
          maxlength="8"
          spellcheck="false"
          class="answer-input"
          placeholder="填写两位十六进制，如 d4"
          :disabled="Boolean(result)"
          @keyup.enter="check"
        />
        <span class="unit">十六进制</span>
      </div>

      <div v-if="!result" class="actions">
        <button
          type="button"
          class="btn primary"
          :disabled="!answer.trim() || submitting"
          @click="check"
        >
          {{ submitting ? '判分中…' : '提交答案' }}
        </button>
        <button type="button" class="btn ghost" :disabled="loading" @click="next">
          换一题
        </button>
      </div>

      <div v-else class="feedback" :class="{ ok: result.isCorrect }">
        <p class="verdict">
          {{ result.isCorrect ? '✓ 回答正确' : '✗ 回答错误' }}
          <span class="expected">正确答案：{{ result.expected }}</span>
        </p>
        <p class="analysis">{{ result.analysis }}</p>
        <div class="actions">
          <button type="button" class="btn" @click="next">下一题</button>
          <button
            v-if="result.stepIndex != null"
            type="button"
            class="btn ghost"
            @click="gotoStep"
          >
            跳到该步动画
          </button>
        </div>
      </div>
    </div>

    <p v-else-if="loading" class="loading">出题中…</p>
  </div>
</template>

<style scoped>
.exercise-view {
  max-width: 860px;
  margin: 0 auto;
  padding: 32px 20px 64px;
}

.head h1 {
  margin: 0 0 8px;
  font-size: 24px;
  color: #111827;
}

.sub {
  margin: 0 0 20px;
  font-size: 13px;
  color: #6b7280;
}

.type-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
}

.tab {
  padding: 8px 18px;
  border: 1px solid #e5e7eb;
  border-radius: 9px;
  background: #ffffff;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
}

.tab.active {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #ffffff;
  font-weight: 600;
}

.card {
  padding: 22px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
}

.prompt {
  margin: 0 0 18px;
  font-size: 14px;
  line-height: 1.8;
  color: #1f2937;
}

.matrices {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: center;
  margin-bottom: 20px;
}

.arrow {
  font-size: 20px;
  color: #d1d5db;
}

.options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.option {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #ffffff;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  font-family: 'Consolas', monospace;
}

.option:hover:not(:disabled) {
  border-color: #a5b4fc;
}

.option.picked {
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
}

.option.correct {
  background: #ecfdf5;
  border-color: #10b981;
  color: #065f46;
  font-weight: 600;
}

.option.wrong {
  background: #fef2f2;
  border-color: #ef4444;
  color: #991b1b;
}

.fill {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.answer-input {
  padding: 9px 12px;
  width: 200px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-family: 'Consolas', monospace;
  font-size: 14px;
  outline: none;
}

.answer-input:focus {
  border-color: #a5b4fc;
}

.unit {
  font-size: 12px;
  color: #9ca3af;
}

.actions {
  display: flex;
  gap: 10px;
}

.btn {
  padding: 8px 18px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
}

.btn.primary {
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

.feedback {
  padding: 16px;
  border-radius: 10px;
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.feedback.ok {
  background: #ecfdf5;
  border-color: #a7f3d0;
}

.verdict {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: #991b1b;
}

.feedback.ok .verdict {
  color: #065f46;
}

.expected {
  margin-left: 10px;
  font-size: 12px;
  font-weight: 400;
  color: #6b7280;
}

.analysis {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.8;
  color: #4b5563;
}

.notice {
  padding: 14px 16px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
  font-size: 13px;
  color: #92400e;
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