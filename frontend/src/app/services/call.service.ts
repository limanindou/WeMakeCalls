import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AgentDTO, CallSessionDTO, FeedbackRequest } from '../models/interfaces';

@Injectable({ providedIn: 'root' })
export class CallService {
  private http = inject(HttpClient);
  private baseUrl = 'http://localhost:5000';

  getAvailableAgents(): Observable<AgentDTO[]> {
    return this.http.get<AgentDTO[]>(`${this.baseUrl}/agents/available`);
  }

  startCall(): Observable<CallSessionDTO> {
    return this.http.post<CallSessionDTO>(`${this.baseUrl}/calls/start`, {});
  }

  endCall(callId: string): Observable<CallSessionDTO> {
    return this.http.post<CallSessionDTO>(`${this.baseUrl}/calls/end/${callId}`, {});
  }

  submitFeedback(callId: string, feedback: FeedbackRequest): Observable<CallSessionDTO> {
    return this.http.post<CallSessionDTO>(`${this.baseUrl}/calls/feedback/${callId}`, feedback);
  }

  getCallHistory(): Observable<CallSessionDTO[]> {
    return this.http.get<CallSessionDTO[]>(`${this.baseUrl}/calls/history`);
  }
}
