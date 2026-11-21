import { CurrencyPipe, DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, catchError, forkJoin, map, of, switchMap } from 'rxjs';
import { describeApiError } from './api-error';
import { ExpenseForm } from './expense-form';
import { Category, Expense, LedgerApi, MonthlySummary } from './ledger-api';
import { formatMonth, isMonth, shiftMonth, toMonth } from './month';
import { PartnerIncome } from './partner-income';

interface MonthLedger {
  categories: Category[];
  summary: MonthlySummary;
  expenses: Expense[];
}

@Component({
  selector: 'app-ledger-page',
  imports: [CurrencyPipe, DatePipe, ExpenseForm, PartnerIncome],
  templateUrl: './ledger-page.html',
  styleUrl: './ledger-page.scss',
})
export class LedgerPage implements OnInit {
  private readonly api = inject(LedgerApi);
  private readonly loads = new Subject<string>();

  protected readonly month = signal(toMonth(new Date()));
  protected readonly monthLabel = computed(() => formatMonth(this.month()));
  protected readonly ledger = signal<MonthLedger | null>(null);
  protected readonly visibleLedger = computed(() => {
    const ledger = this.ledger();
    return ledger?.summary.month === this.month() ? ledger : null;
  });
  protected readonly loadError = signal<string | null>(null);

  constructor() {
    this.loads
      .pipe(
        switchMap((month) =>
          forkJoin({
            categories: this.api.getCategories(),
            summary: this.api.getSummary(month),
            expenses: this.api.getExpenses(month),
          }).pipe(
            map((ledger) => ({ ledger, error: null })),
            catchError((error: unknown) => of({ ledger: null, error: describeApiError(error) })),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe(({ ledger, error }) => {
        this.ledger.set(ledger);
        this.loadError.set(error);
      });
  }

  ngOnInit(): void {
    this.reload();
  }

  protected reload(): void {
    this.loads.next(this.month());
  }

  protected selectMonth(month: string): void {
    if (isMonth(month)) {
      this.month.set(month);
      this.reload();
    }
  }

  protected moveMonth(offset: number): void {
    this.selectMonth(shiftMonth(this.month(), offset));
  }

  protected showExpenseMonth(expense: Expense): void {
    this.selectMonth(expense.transaction_date.slice(0, 7));
  }

  protected isNegative(amount: string): boolean {
    return amount.startsWith('-');
  }
}
