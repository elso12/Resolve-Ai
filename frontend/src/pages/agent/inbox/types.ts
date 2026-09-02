export type TicketStatus =
  | 'open'
  | 'assigned'
  | 'in_progress'
  | 'waiting_for_customer'
  | 'resolved'
  | 'closed';

export type TicketPriority = 'low' | 'medium' | 'high' | 'critical';

export type TicketCategory = 'billing' | 'technical' | 'account' | 'general';

export type ActionStatus = 'pending_approval' | 'approved' | 'rejected' | 'executed';
export type ActionRiskLevel = 'low' | 'high';

export interface ActionProposal {
  id: number;
  ticket_id: number;
  tool_name: string;
  parameters: Record<string, any>;
  estimated_cost: number;
  status: ActionStatus;
  risk_level: ActionRiskLevel;
  result?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface MessageSender {
  id: number;
  email: string;
  full_name: string;
  role: string;
}

export interface Message {
  id: string | number;
  ticket_id?: number;
  sender_id?: number;
  sender?: MessageSender | 'CUSTOMER' | 'AGENT' | 'SYSTEM' | string;
  agentName?: string;
  body?: string;
  text?: string;
  timestamp?: string;
  created_at?: string;
  is_internal?: boolean;
  isInternal?: boolean;
}

export interface Ticket {
  id: number | string;
  ticket_number: string;
  subject: string;
  description?: string;
  status: TicketStatus;
  priority: TicketPriority;
  category: TicketCategory | string;
  customer_id?: number;
  assigned_agent_id?: number | null;
  organization_id?: number;
  created_at?: string;
  updated_at?: string;
  first_response_due_at?: string | null;
  resolution_due_at?: string | null;
  first_responded_at?: string | null;
  resolved_at?: string | null;
  sla_first_response_breached?: boolean;
  sla_resolution_breached?: boolean;

  // UI convenience attributes
  customerName?: string;
  customerEmail?: string;
  customerPlan?: string;
  customerTicketCount?: number;
  assignee?: string;
  updatedAt?: string;
  messages?: Message[];
  actions?: ActionProposal[];
}

export type QueueType = 'all' | 'assigned' | 'unassigned' | 'high_priority' | 'resolved';

export interface Queue {
  id: QueueType;
  label: string;
  icon: any;
  count: number;
}
