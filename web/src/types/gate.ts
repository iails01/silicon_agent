export interface Gate {
  id: string;
  gate_type: string;
  task_id: string;
  agent_role: string;
  content: Record<string, string> | null;
  status: 'pending' | 'approved' | 'rejected' | 'revised';
  reviewer: string | null;
  review_comment: string | null;
  created_at: string;
  reviewed_at: string | null;
  // Phase 1.3: Retry tracking
  retry_count?: number;
  // Phase 2.3: Dynamic gate flag
  is_dynamic?: boolean;
  // Phase 2.4: Revised content
  revised_content?: string | null;
}

export interface GateApproveRequest {
  reviewer?: string;
  comment?: string;
}

export interface GateRejectRequest {
  reviewer?: string;
  comment: string;
}

export interface GateReviseRequest {
  reviewer?: string;
  comment: string;
  revised_content?: string;
}
