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
    path: 'analytics',
    loadComponent: () => import('./pages/analytics/analytics').then((m) => m.AnalyticsPage),
    title: 'Analytics — Marketing Compliance Checker',
  },
  {
    path: 'youtube',
    loadComponent: () => import('./pages/youtube/youtube').then((m) => m.YouTubePage),
    title: 'YouTube surveillance — Marketing Compliance Checker',
  },
  {
    path: 'graph',
    loadComponent: () => import('./pages/graph/graph').then((m) => m.GraphPage),
    title: 'Knowledge graph — Marketing Compliance Checker',
  },
  {
    path: 'benchmark',
    loadComponent: () => import('./pages/bench/bench').then((m) => m.BenchPage),
    title: 'Benchmark — Marketing Compliance Checker',
  },
  {
    path: 'experiments',
    loadComponent: () => import('./pages/experiments/experiments').then((m) => m.ExperimentsPage),
    title: 'Experiments — Marketing Compliance Checker',
  },
  {
    path: 'help',
    loadComponent: () => import('./pages/help/help').then((m) => m.HelpPage),
    title: 'User manual — Marketing Compliance Checker',
  },
  {
    path: 'reports/:id',
    loadComponent: () => import('./pages/report/report').then((m) => m.ReportPage),
    title: 'Report — Marketing Compliance Checker',
  },
  { path: '**', redirectTo: '' },
];
