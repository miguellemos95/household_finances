import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { environment } from '../environments/environment';

describe('App', () => {
  let httpTestingController: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTestingController.verify();
  });

  it('should show a connected API when the health check succeeds', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const request = httpTestingController.expectOne(`${environment.apiBaseUrl}/health/live`);
    request.flush({ status: 'ok' });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('API connected');
  });

  it('should show an unavailable API when the health check fails', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const request = httpTestingController.expectOne(`${environment.apiBaseUrl}/health/live`);
    request.flush({}, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('API unavailable');
  });
});
