/** 历史记录接口 */

import { api } from './client';
import type { PagedResult, SessionSummary, Trace } from '../types/trace';

export function listSessions(
  page = 1,
  size = 20,
): Promise<PagedResult<SessionSummary>> {
  return api.get<PagedResult<SessionSummary>>(
    `/api/history/sessions?page=${page}&size=${size}`,
    true,
  );
}

export function getSessionDetail(
  id: number,
): Promise<{ meta: SessionSummary; trace: Trace }> {
  return api.get<{ meta: SessionSummary; trace: Trace }>(
    `/api/history/sessions/${id}`,
    true,
  );
}

export function deleteSession(id: number): Promise<void> {
  return api.del<void>(`/api/history/sessions/${id}`, true);
}