export interface AgentDTO {
  agentId: string;
  name: string;
}

export interface CallSessionDTO {
  callId: string;
  agentId: string;
  agentName: string;
  callStarted: string;
  callEnded: string | null;
  durationSeconds: number | null;
  hangupReason: string | null;
  agentRating: number | null;
  status: 'ACTIVE' | 'COMPLETED';
}

export interface FeedbackRequest {
  hangupReason: string;
  agentRating: number;
}

export interface TimerMessage {
  callId: string;
  elapsedSeconds: number;
}

export type HangupReason =
  | 'Issue Resolved'
  | 'Wrong Department'
  | 'Long Wait Time'
  | 'Call Dropped'
  | 'Other';

export const HANGUP_REASONS: HangupReason[] = [
  'Issue Resolved',
  'Wrong Department',
  'Long Wait Time',
  'Call Dropped',
  'Other'
];
