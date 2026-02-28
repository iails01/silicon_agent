import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listTasks, createTask, cancelTask, retryTask, retryTaskFromStage, retryTasksBatch, getTask } from '@/services/taskApi';
import type { TaskCreateRequest, TaskBatchRetryRequest, TaskRetryFromStageRequest } from '@/types/task';

export function useTaskList(params?: {
  status?: string;
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  project_id?: string;
  title?: string;
}) {
  return useQuery({
    queryKey: ['tasks', params],
    queryFn: () => listTasks(params),
  });
}

export function useTask(id: string) {
  return useQuery({
    queryKey: ['task', id],
    queryFn: () => getTask(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const task = query.state.data;
      return task?.status === 'running' ? 3000 : false;
    },
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: TaskCreateRequest) => createTask(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useCancelTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelTask(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] });
      qc.invalidateQueries({ queryKey: ['cockpit'] });
    },
  });
}

export function useRetryTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryTask(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ['task', id] });
      qc.invalidateQueries({ queryKey: ['tasks'] });
      qc.invalidateQueries({ queryKey: ['cockpit'] });
    },
  });
}

/**
 * Retry a failed task from the specified failed stage.
 * @returns Mutation object for stage-level task retry.
 */
export function useRetryTaskFromStage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, req }: { id: string; req: TaskRetryFromStageRequest }) => retryTaskFromStage(id, req),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['task', vars.id] });
      qc.invalidateQueries({ queryKey: ['tasks'] });
      qc.invalidateQueries({ queryKey: ['cockpit'] });
    },
  });
}

/**
 * Retry multiple failed tasks in batch.
 * @returns Mutation object for batch task retry.
 */
export function useBatchRetryTasks() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: TaskBatchRetryRequest) => retryTasksBatch(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] });
      qc.invalidateQueries({ queryKey: ['cockpit'] });
    },
  });
}
