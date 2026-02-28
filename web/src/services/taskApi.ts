import api from './api';
import type {
  Task,
  TaskListResponse,
  TaskCreateRequest,
  TaskStage,
  TaskDecomposeRequest,
  TaskDecomposeResponse,
  TaskBatchCreateRequest,
  TaskBatchCreateResponse,
  TaskRetryFromStageRequest,
  TaskBatchRetryRequest,
  TaskBatchRetryResponse,
} from '@/types/task';

export async function listTasks(params?: {
  status?: string;
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  project_id?: string;
  title?: string;
}): Promise<TaskListResponse> {
  const { data } = await api.get<{ items: Task[]; total: number; page: number; page_size: number }>('/tasks', { params });
  return { tasks: data.items, total: data.total, page: data.page, page_size: data.page_size };
}

export async function createTask(req: TaskCreateRequest): Promise<Task> {
  const { data } = await api.post<Task>('/tasks', req);
  return data;
}

export async function getTask(id: string): Promise<Task> {
  const { data } = await api.get<Task>(`/tasks/${id}`);
  return data;
}

export async function getTaskStages(id: string): Promise<TaskStage[]> {
  const { data } = await api.get<TaskStage[]>(`/tasks/${id}/stages`);
  return data;
}

export async function cancelTask(id: string): Promise<void> {
  await api.post(`/tasks/${id}/cancel`);
}

export async function retryTask(id: string): Promise<void> {
  await api.post(`/tasks/${id}/retry`);
}

/**
 * Retry task execution from a specific failed stage.
 * @param id Task identifier.
 * @param req Stage retry payload.
 * @returns Latest task snapshot after retry is scheduled.
 */
export async function retryTaskFromStage(id: string, req: TaskRetryFromStageRequest): Promise<Task> {
  const { data } = await api.post<Task>(`/tasks/${id}/retry-from-stage`, req);
  return data;
}

/**
 * Retry multiple failed tasks in a single request.
 * @param req Batch retry payload.
 * @returns Batch retry result summary and per-task outcomes.
 */
export async function retryTasksBatch(req: TaskBatchRetryRequest): Promise<TaskBatchRetryResponse> {
  const { data } = await api.post<TaskBatchRetryResponse>('/tasks/retry-batch', req);
  return data;
}

export async function decomposePrd(req: TaskDecomposeRequest): Promise<TaskDecomposeResponse> {
  const { data } = await api.post<TaskDecomposeResponse>('/tasks/decompose', req);
  return data;
}

export async function batchCreateTasks(req: TaskBatchCreateRequest): Promise<TaskBatchCreateResponse> {
  const { data } = await api.post<TaskBatchCreateResponse>('/tasks/batch', req);
  return data;
}
