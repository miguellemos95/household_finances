import { HttpErrorResponse } from '@angular/common/http';

interface ApiErrorDetail {
  message?: string;
  errors?: { field: string; message: string }[];
}

export function describeApiError(error: unknown): string {
  if (!(error instanceof HttpErrorResponse) || error.status === 0) {
    return 'The API could not be reached.';
  }
  const detail: ApiErrorDetail | undefined = error.error?.detail;
  if (!detail?.message) {
    return 'The request could not be completed.';
  }
  const fieldMessages = (detail.errors ?? [])
    .filter((issue) => issue.message !== detail.message)
    .map((issue) => `${issue.field}: ${issue.message}`);
  return [detail.message, ...fieldMessages].join(' ');
}
