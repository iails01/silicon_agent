import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listGates, approveGate, rejectGate, reviseGate } from '@/services/gateApi';
import type { GateApproveRequest, GateRejectRequest, GateReviseRequest } from '@/types/gate';

export function useGateList(params?: { status?: string; task_id?: string }) {
  return useQuery({
    queryKey: ['gates', params],
    queryFn: () => listGates(params),
    refetchInterval: 10_000,
  });
}

export function useApproveGate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, req }: { id: string; req?: GateApproveRequest }) => approveGate(id, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gates'] });
    },
  });
}

export function useRejectGate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, req }: { id: string; req: GateRejectRequest }) => rejectGate(id, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gates'] });
    },
  });
}

export function useReviseGate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, req }: { id: string; req: GateReviseRequest }) => reviseGate(id, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gates'] });
    },
  });
}
