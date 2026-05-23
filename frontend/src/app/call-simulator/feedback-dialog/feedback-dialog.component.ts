import { Component, input, output, model, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { SelectModule } from 'primeng/select';
import { RatingModule } from 'primeng/rating';
import { ButtonModule } from 'primeng/button';
import { FeedbackRequest, HANGUP_REASONS } from '../../models/interfaces';

@Component({
  selector: 'app-feedback-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule, DialogModule, SelectModule, RatingModule, ButtonModule],
  templateUrl: './feedback-dialog.component.html',
  styleUrl: './feedback-dialog.component.scss'
})
export class FeedbackDialogComponent {
  visible = model.required<boolean>();
  callId = input.required<string>();
  feedbackSubmitted = output<FeedbackRequest>();

  hangupReasons = HANGUP_REASONS.map(r => ({ label: r, value: r }));
  selectedReason = signal<string>('');
  agentRating = signal<number>(0);

  submit(): void {
    if (!this.selectedReason() || this.agentRating() < 1) return;

    this.feedbackSubmitted.emit({
      hangupReason: this.selectedReason(),
      agentRating: this.agentRating()
    });

    this.selectedReason.set('');
    this.agentRating.set(0);
  }
}
