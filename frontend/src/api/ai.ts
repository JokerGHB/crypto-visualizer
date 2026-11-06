/** AI 辅导接口 */

import { streamPost } from './client';
import type { Step } from '../types/trace';

/** 把 Step 转成后端要求的 stepContext */
export function toStepContext(
  step: Step,
  options: { keyBits: number; mode: string; explain: string },
): Record<string, unknown> {
  return {
    index: step.index,
    round: step.round,
    op: step.op,
    stateBefore: step.stateBefore,
    stateAfter: step.stateAfter,
    cells: step.cells.slice(0, 8),
    explain: step.explain,
    keyBits: options.keyBits,
    mode: options.mode,
  };
}

export interface ChatOptions {
  conversationId: number | null;
  stepContext: Record<string, unknown>;
  question: string;
  totalSteps?: number;
}

/** 发起流式对话 */
export function chatStream(
  options: ChatOptions,
  onDelta: (text: string) => void,
  onConversation: (id: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamPost(
    '/api/ai/tutor/chat',
    {
      conversationId: options.conversationId,
      stepContext: options.stepContext,
      question: options.question,
      totalSteps: options.totalSteps,
    },
    onDelta,
    onConversation,
    signal,
  );
}