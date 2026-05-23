import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { ChartModule } from 'primeng/chart';
import { CallService } from '../../services/call.service';
import { CallSessionDTO } from '../../models/interfaces';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [CommonModule, CardModule, ChartModule],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.scss'
})
export class AnalyticsComponent implements OnInit {
  private callService = inject(CallService);

  durationData = signal<any>(null);
  hangupData = signal<any>(null);
  ratingData = signal<any>(null);

  chartOptions = {
    plugins: {
      legend: { labels: { color: '#e0e0e0' } }
    },
    scales: {
      x: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } },
      y: { ticks: { color: '#e0e0e0' }, grid: { color: '#333' } }
    }
  };

  pieOptions = {
    plugins: {
      legend: { labels: { color: '#e0e0e0' } }
    }
  };

  ngOnInit(): void {
    this.callService.getCallHistory().subscribe({
      next: (calls) => this.computeChartData(calls)
    });
  }

  private computeChartData(calls: CallSessionDTO[]): void {
    const completed = calls.filter(c => c.status === 'COMPLETED');

    // Duration histogram
    const buckets = [0, 0, 0, 0];
    for (const call of completed) {
      if (call.durationSeconds === null) continue;
      if (call.durationSeconds <= 30) buckets[0]++;
      else if (call.durationSeconds <= 60) buckets[1]++;
      else if (call.durationSeconds <= 120) buckets[2]++;
      else buckets[3]++;
    }
    this.durationData.set({
      labels: ['0-30s', '30-60s', '60-120s', '120s+'],
      datasets: [{ label: 'Calls', data: buckets, backgroundColor: '#00cc00' }]
    });

    // Hangup reasons pie
    const reasons = new Map<string, number>();
    for (const call of completed) {
      if (!call.hangupReason) continue;
      reasons.set(call.hangupReason, (reasons.get(call.hangupReason) || 0) + 1);
    }
    this.hangupData.set({
      labels: [...reasons.keys()],
      datasets: [{
        data: [...reasons.values()],
        backgroundColor: ['#00ff00', '#00cc00', '#009900', '#006600', '#003300']
      }]
    });

    // Rating distribution
    const ratings = [0, 0, 0, 0, 0];
    for (const call of completed) {
      if (call.agentRating === null) continue;
      ratings[call.agentRating - 1]++;
    }
    this.ratingData.set({
      labels: ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars'],
      datasets: [{ label: 'Ratings', data: ratings, backgroundColor: '#00ff00' }]
    });
  }
}
