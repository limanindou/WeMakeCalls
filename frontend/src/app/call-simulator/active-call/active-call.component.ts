import { Component, input, output, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { CallSessionDTO } from '../../models/interfaces';

@Component({
  selector: 'app-active-call',
  standalone: true,
  imports: [CommonModule, ButtonModule, CardModule],
  templateUrl: './active-call.component.html',
  styleUrl: './active-call.component.scss'
})
export class ActiveCallComponent {
  call = input.required<CallSessionDTO>();
  elapsedSeconds = input.required<number>();
  endCall = output<void>();

  formattedTime = computed(() => {
    const secs = this.elapsedSeconds();
    const mins = Math.floor(secs / 60);
    const remainingSecs = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${remainingSecs.toString().padStart(2, '0')}`;
  });
}
