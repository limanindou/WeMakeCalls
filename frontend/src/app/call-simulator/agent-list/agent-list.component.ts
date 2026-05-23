import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { TagModule } from 'primeng/tag';
import { AgentDTO } from '../../models/interfaces';

@Component({
  selector: 'app-agent-list',
  standalone: true,
  imports: [CommonModule, CardModule, TagModule],
  templateUrl: './agent-list.component.html',
  styleUrl: './agent-list.component.scss'
})
export class AgentListComponent {
  agents = input.required<AgentDTO[]>();
}
