import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { CallService } from '../../services/call.service';
import { AgentDTO } from '../../models/interfaces';

@Component({
  selector: 'app-agent-management',
  standalone: true,
  imports: [CommonModule, TableModule, TagModule],
  templateUrl: './agent-management.component.html',
  styleUrl: './agent-management.component.scss'
})
export class AgentManagementComponent implements OnInit {
  private callService = inject(CallService);
  agents = signal<AgentDTO[]>([]);
  loading = signal<boolean>(true);

  ngOnInit(): void {
    this.callService.getAvailableAgents().subscribe({
      next: (agents) => {
        this.agents.set(agents);
        this.loading.set(false);
      },
      error: () => this.loading.set(false)
    });
  }
}
