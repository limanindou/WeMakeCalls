import { Routes } from '@angular/router';
import { CallSimulatorComponent } from './call-simulator/call-simulator.component';
import { DashboardComponent } from './dashboard/dashboard.component';
import { CallHistoryComponent } from './dashboard/call-history/call-history.component';
import { AgentManagementComponent } from './dashboard/agent-management/agent-management.component';
import { AnalyticsComponent } from './dashboard/analytics/analytics.component';

export const routes: Routes = [
  { path: '', redirectTo: '/call', pathMatch: 'full' },
  { path: 'call', component: CallSimulatorComponent },
  {
    path: 'dashboard',
    component: DashboardComponent,
    children: [
      { path: '', redirectTo: 'history', pathMatch: 'full' },
      { path: 'history', component: CallHistoryComponent },
      { path: 'agents', component: AgentManagementComponent },
      { path: 'analytics', component: AnalyticsComponent }
    ]
  }
];
