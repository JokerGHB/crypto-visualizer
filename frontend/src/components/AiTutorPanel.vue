<script setup lang="ts">
/**
 * AI 辅导面板。
 *
 * 关键约束：每次提问都带上"当前停留在哪一步"的上下文，
 * 因此用户停在哪一步就能问哪一步，回答始终与画面同步。
 */
import { computed, nextTick, ref, watch } from 'vue';
import { chatStream, toStepContext } from '../api/ai';
import type { Step } from '../types/trace';
import { OP_LABELS } from '../types/trace';

interface Props {
  /** 当前步骤；为 null 时禁用提问 */
  step: Step | null;
  keyBits: number;
  mode: string;
  totalSteps: number;
}

const props = defineProps<Props>();

interface Message {
  role: 'user' | 'assistant';
  content: string;
  /** 是否为离线降级内容 */
  offline?: boolean;
}

const messages = ref<Message[]>([]);
const input = ref('');
const streaming = ref(false);
const error = ref<string | null>(null);
const conversationId = ref<number | null>(null);
const listEl = ref<HTMLElement | null>(null);

let controller: AbortController | null = null;

const canAsk = computed(
  () => Boolean(props.step) && !streaming.value && input.value.trim().length > 0,
);

const stepLabel = computed(() => {
  if (!props.step) {
    return '未加载';
  }
  return `第 ${props.step.round} 轮 ${OP_LABELS[props.step.op]}（第 ${props.step.index + 1}/${props.totalSteps} 步）`;
});

/** 切换步骤时清空对话，避免上下文错位 */
watch(
  () => props.step?.index,
  () => {
    if (messages.value.length > 0) {
      messages.value = [];
      conversationId.value = null;
    }
  },
);

async function scrollToBottom(): Promise<void> {
  await nextTick();
  if (listEl.value) {
    listEl.value.scrollTop = listEl.value.scrollHeight;
  }
}

async function send(): Promise<void> {
  if (!canAsk.value || !props.step) {
    return;
  }
  const question = input.value.trim();
  input.value = '';
  error.value = null;
  messages.value.push({ role: 'user', content: question });
  const assistantIndex = messages.value.push({
    role: 'assistant',
    content: '',
  }) - 1;

  streaming.value = true;
  controller = new AbortController();
  await scrollToBottom();

  try {
    await chatStream(
      {
        conversationId: conversationId.value,
        stepContext: toStepContext(props.step, {
          keyBits: props.keyBits,
          mode: props.mode,
          explain: props.step.explain,
        }),
        question,
        totalSteps: props.totalSteps,
      },
      (delta) => {
        messages.value[assistantIndex].content += delta;
        void scrollToBottom();
      },
      (id) => {
        conversationId.value = id;
      },
      controller.signal,
    );
    const final = messages.value[assistantIndex].content;
    if (final.includes('离线讲解')) {
      messages.value[assistantIndex].offline = true;
    }
  } catch (err) {
    if ((err as Error).name === 'AbortError') {
      messages.value[assistantIndex].content += '\n\n（已停止）';
    } else {
      error.value = (err as Error).message;
      // 失败时移除空占位，避免出现空白气泡
      if (!messages.value[assistantIndex].content) {
        messages.value.splice(assistantIndex, 1);
      }
    }
  } finally {
    streaming.value = false;
    controller = null;
    await scrollToBottom();
  }
}

function stop(): void {
  controller?.abort();
}

function clearChat(): void {
  messages.value = [];
  conversationId.value = null;
  error.value = null;
}

/** 快捷键：Enter 发送，Shift+Enter 换行 */
function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    void send();
  }
}
</script>

<template>
  <aside class="ai-panel">
    <header class="panel-head">
      <div class="title-row">
        <h3>AI 辅导</h3>
        <span class="context" :class="{ muted: !step }">{{ stepLabel }}</span>
      </div>
      <button
        v-if="messages.length > 0"
        type="button"
        class="link-btn"
        @click="clearChat"
      >
        清空
      </button>
    </header>

    <p v-if="!step" class="placeholder">请先在上方载入一次加解密过程。</p>

    <div ref="listEl" class="messages">
      <p v-if="messages.length === 0 && step" class="placeholder">
        停在哪一步，就能问哪一步。例如：<br />
        「为什么这个字节要从 {{ step.cells[0]?.before ?? '19' }} 变成
        {{ step.cells[0]?.after ?? 'd4' }}？」
      </p>

      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="bubble"
        :class="msg.role"
      >
        <span v-if="msg.offline" class="offline-tag">离线</span>
        <span class="content">{{ msg.content || (streaming ? '思考中…' : '') }}</span>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <footer class="composer">
      <textarea
        v-model="input"
        :disabled="!step || streaming"
        rows="2"
        placeholder="问点关于当前步骤的问题…（Enter 发送，Shift+Enter 换行）"
        @keydown="onKeydown"
      />
      <div class="composer-actions">
        <button
          v-if="streaming"
          type="button"
          class="btn stop"
          @click="stop"
        >
          停止
        </button>
        <button
          type="button"
          class="btn send"
          :disabled="!canAsk"
          @click="send"
        >
          发送
        </button>
      </div>
    </footer>
  </aside>
</template>

<style scoped>
.ai-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 420px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  overflow: hidden;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #f1f5f9;
}

.title-row {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.title-row h3 {
  margin: 0;
  font-size: 14px;
  color: #111827;
}

.context {
  font-size: 11px;
  color: #4f46e5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.context.muted {
  color: #9ca3af;
}

.link-btn {
  border: none;
  background: none;
  color: #9ca3af;
  font-size: 11.5px;
  cursor: pointer;
  flex-shrink: 0;
}

.link-btn:hover {
  color: #4f46e5;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.placeholder {
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
  color: #9ca3af;
}

.bubble {
  max-width: 92%;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 12.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble.user {
  align-self: flex-end;
  background: #4f46e5;
  color: #ffffff;
}

.bubble.assistant {
  align-self: flex-start;
  background: #f8fafc;
  color: #1f2937;
  border: 1px solid #f1f5f9;
}

.offline-tag {
  display: inline-block;
  margin-bottom: 4px;
  padding: 1px 6px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 4px;
  font-size: 10px;
}

.error {
  margin: 0;
  font-size: 12px;
  color: #b91c1c;
}

.composer {
  padding: 10px 12px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.composer textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 12.5px;
  font-family: inherit;
  line-height: 1.6;
  resize: none;
  outline: none;
}

.composer textarea:focus {
  border-color: #a5b4fc;
}

.composer textarea:disabled {
  background: #f9fafb;
  color: #9ca3af;
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn {
  padding: 6px 16px;
  border-radius: 8px;
  font-size: 12.5px;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn.send {
  background: #4f46e5;
  color: #ffffff;
}

.btn.send:disabled {
  background: #c7d2fe;
  cursor: not-allowed;
}

.btn.stop {
  background: #ffffff;
  border-color: #d1d5db;
  color: #6b7280;
}
</style>