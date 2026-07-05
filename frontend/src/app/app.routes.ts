import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/dashboard/dashboard').then((m) => m.DashboardPage),
    title: 'Marketing Compliance Checker',
  },
  {
    path: 'analyze',
    loadComponent: () => import('./pages/analyze/analyze').then((m) => m.AnalyzePage),
    title: 'New analysis — Marketing Compliance Checker',
  },
  {
    path: 'reports/:id',
    loadComponent: () => import('./pages/report/report').then((m) => m.ReportPage),
    title: 'Report — Marketing Compliance Checker',
  },
  { path: '**', redirectTo: '' },
];
