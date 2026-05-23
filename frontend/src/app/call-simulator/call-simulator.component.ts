import { Component, inject, signal, computed, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { CallService } from '../services/call.service';
import { WebSocketService } from '../services/websocket.service';
import { AgentDTO, CallSessionDTO, FeedbackRequest } from '../models/interfaces';
import { AgentListComponent } from './agent-list/agent-list.component';
import { ActiveCallComponent } from './active-call/active-call.component';
import { FeedbackDialogComponent } from './feedback-dialog/feedback-dialog.component';

@Component({
  selector: 'app-call-simulator',
  standalone: true,
  imports: [
    CommonModule, ButtonModule, CardModule, ToastModule,
    AgentListComponent, ActiveCallComponent, FeedbackDialogComponent
  ],
  providers: [MessageService],
  templateUrl: './call-simulator.component.html',
  styleUrl: './call-simulator.component.scss'
})
export class CallSimulatorComponent implements OnInit, OnDestroy {
  private callService = inject(CallService);
  private wsService = inject(WebSocketService);
  private messageService = inject(MessageService);
  private timerSubscription?: Subscription;

  availableAgents = signal<AgentDTO[]>([]);
  activeCall = signal<CallSessionDTO | null>(null);
  elapsedSeconds = signal<number>(0);
  isCallActive = computed(() => this.activeCall() !== null && this.activeCall()!.status === 'ACTIVE');
  showFeedbackDialog = signal<boolean>(false);
  loading = signal<boolean>(false);

  ngOnInit(): void {
    this.loadAvailableAgents();
    this.wsService.connect();
  }

  ngOnDestroy(): void {
    this.timerSubscription?.unsubscribe();
  }

  loadAvailableAgents(): void {
    this.callService.getAvailableAgents().subscribe({
      next: (agents) => this.availableAgents.set(agents),
      error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to load agents' })
    });
  }

  startCall(): void {
    this.loading.set(true);
    this.callService.startCall().subscribe({
      next: (session) => {
        this.activeCall.set(session);
        this.elapsedSeconds.set(0);
        this.loading.set(false);

        this.timerSubscription = this.wsService
          .subscribeToTimer(session.callId)
          .subscribe((msg) => this.elapsedSeconds.set(msg.elapsedSeconds));
      },
      error: (err) => {
        this.loading.set(false);
        if (err.status === 409) {
          this.messageService.add({ severity: 'warn', summary: 'No Agents', detail: 'No agents available. Try again later.' });
        } else {
          this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to start call' });
        }
      }
    });
  }

  endCall(): void {
    const callId = this.activeCall()!.callId;
    this.timerSubscription?.unsubscribe();

    this.callService.endCall(callId).subscribe({
      next: (session) => {
        this.activeCall.set(session);
        this.showFeedbackDialog.set(true);
      },
      error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to end call' })
    });
  }

  onFeedbackSubmitted(feedback: FeedbackRequest): void {
    const callId = this.activeCall()!.callId;
    this.callService.submitFeedback(callId, feedback).subscribe({
      next: () => {
        this.activeCall.set(null);
        this.elapsedSeconds.set(0);
        this.showFeedbackDialog.set(false);
        this.loadAvailableAgents();
        this.messageService.add({ severity: 'success', summary: 'Done', detail: 'Feedback submitted' });
      },
      error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to submit feedback' })
    });
  }
}
