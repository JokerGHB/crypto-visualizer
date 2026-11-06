/** 练习模式接口 */

import { api } from './client';
import type { Exercise, ExerciseResult } from '../types/trace';

export function generateExercise(
  type: string,
  difficulty = 'easy',
): Promise<Exercise> {
  return api.post<Exercise>('/api/exercise/generate', { type, difficulty }, true);
}

export function submitAnswer(
  exerciseId: number,
  answer: string,
): Promise<ExerciseResult> {
  return api.post<ExerciseResult>(
    '/api/exercise/submit',
    { exerciseId, answer },
    true,
  );
}

export function listExerciseTypes(): Promise<{ type: string; label: string }[]> {
  return api.get<{ type: string; label: string }[]>('/api/exercise/types');
}