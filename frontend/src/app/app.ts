import { Component, OnInit, inject, signal } from '@angular/core';
import { HealthApi } from './health-api';

@Component({
  selector: 'app-root',
  templateUrl: './app-status.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  private readonly healthApi = inject(HealthApi);
  protected readonly apiStatus = signal<'checking' | 'online' | 'offline'>('checking');

  ngOnInit(): void {
    this.healthApi.checkLive().subscribe({
      next: () => this.apiStatus.set('online'),
      error: () => this.apiStatus.set('offline')
    });
  }
}
