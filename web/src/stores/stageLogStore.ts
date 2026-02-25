import { create } from 'zustand';
import type { WSStageLogPayload } from '@/types/websocket';

interface StageLogState {
  /** logs keyed by stage_id */
  logsByStage: Record<string, WSStageLogPayload[]>;
  addLog: (log: WSStageLogPayload) => void;
  clearTask: (taskId: string) => void;
}

const MAX_LOGS_PER_STAGE = 200;

export const useStageLogStore = create<StageLogState>((set) => ({
  logsByStage: {},
  addLog: (log) =>
    set((state) => {
      const key = log.stage_id;
      const existing = state.logsByStage[key] || [];
      const updated = [...existing, log].slice(-MAX_LOGS_PER_STAGE);
      return { logsByStage: { ...state.logsByStage, [key]: updated } };
    }),
  clearTask: (taskId) =>
    set((state) => {
      const next: Record<string, WSStageLogPayload[]> = {};
      for (const [k, v] of Object.entries(state.logsByStage)) {
        if (v.length > 0 && v[0].task_id !== taskId) {
          next[k] = v;
        }
      }
      return { logsByStage: next };
    }),
}));
