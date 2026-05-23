import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { CallService } from '../../services/call.service';
import { CallSessionDTO } from '../../models/interfaces';

@Component({
  selector: 'app-call-history',
  standalone: true,
  imports: [CommonModule, TableModule, TagModule],
  templateUrl: './call-history.component.html',
  styleUrl: './call-history.component.scss'
})
export class CallHistoryComponent implements OnInit {
  private callService = inject(CallService);
  calls = signal<CallSessionDTO[]>([]);
  loading = signal<boolean>(true);

  ngOnInit(): void {
    this.callService.getCallHistory().subscribe({
      next: (calls) => {
        this.calls.set(calls);
        this.loading.set(false);
      },
      error: () => this.loading.set(false)
    });
  }

  getSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast' {
    return status === 'COMPLETED' ? 'success' : 'info';
  }
}
