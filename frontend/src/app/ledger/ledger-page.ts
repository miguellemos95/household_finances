import { CurrencyPipe, DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, catchError, forkJoin, map, of, switchMap } from 'rxjs';
import { describeApiError } from './api-error';
import { ExpenseForm } from './expense-form';
import {
  BillOccurrence,
  Category,
  CategoryBudget,
  Expense,
  LedgerApi,
  MonthlySummary,
} from './ledger-api';
import { formatMonth, isMonth, shiftMonth, toIsoDate, toMonth } from './month';
import { PartnerIncome } from './partner-income';

interface MonthLedger {
  categories: Category[];
  summary: MonthlySummary;
  expenses: Expense[];
  bills: BillOccurrence[];
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
  protected readonly budgetError = signal<string | null>(null);
  protected readonly budgetSaved = signal(false);
  protected readonly billError = signal<string | null>(null);
  protected readonly billSaved = signal(false);
  protected readonly today = toIsoDate(new Date());

  constructor() {
    this.loads
      .pipe(
        switchMap((month) =>
          forkJoin({
            categories: this.api.getCategories(),
            summary: this.api.getSummary(month),
            expenses: this.api.getExpenses(month),
            bills: this.api.getBills(month),
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

  protected setBudget(category: CategoryBudget, amountInput: HTMLInputElement): void {
    const amount = amountInput.value.trim().replace(',', '.');
    if (!/^\d+(?:\.\d{1,2})?$/.test(amount) || Number(amount) <= 0) {
      this.budgetError.set('Enter a budget amount greater than 0.');
      this.budgetSaved.set(false);
      return;
    }
    this.api.setBudget(category.category.id, this.month(), amount).subscribe({
      next: () => {
        this.budgetError.set(null);
        this.budgetSaved.set(true);
        this.reload();
      },
      error: (error: unknown) => {
        this.budgetError.set(describeApiError(error));
        this.budgetSaved.set(false);
      },
    });
  }

  protected budgetLabel(budget: CategoryBudget): string {
    if (budget.state === 'unset') return 'Not set';
    if (budget.state === 'warning') return 'Warning';
    if (budget.state === 'exceeded') return 'Over budget';
    return 'Within budget';
  }

  protected budgetProgress(budget: CategoryBudget): number {
    return Math.min(Number(budget.percent), 100);
  }

  protected recordBill(
    recurrence: HTMLSelectElement,
    dueDate: HTMLInputElement,
    amount: HTMLInputElement,
    category: HTMLSelectElement,
  ): void {
    const parsedAmount = amount.value.trim().replace(',', '.');
    const categoryId = Number(category.value);
    if (
      !dueDate.value ||
      !/^\d+(?:\.\d{1,2})?$/.test(parsedAmount) ||
      Number(parsedAmount) <= 0 ||
      categoryId <= 0
    ) {
      this.billError.set('Enter a due date, an amount greater than 0 and a category.');
      this.billSaved.set(false);
      return;
    }
    this.api
      .recordBill({
        recurrence: recurrence.value as 'one_off' | 'monthly',
        due_date: dueDate.value,
        amount: parsedAmount,
        category_id: categoryId,
        subcategory_id: null,
      })
      .subscribe({
        next: () => {
          this.billError.set(null);
          this.billSaved.set(true);
          this.reload();
        },
        error: (error: unknown) => {
          this.billError.set(describeApiError(error));
          this.billSaved.set(false);
        },
      });
  }

  protected adjustBillAmount(bill: BillOccurrence, amountInput: HTMLInputElement): void {
    const amount = amountInput.value.trim().replace(',', '.');
    if (!/^\d+(?:\.\d{1,2})?$/.test(amount) || Number(amount) <= 0) {
      this.billError.set('Enter a bill amount greater than 0.');
      return;
    }
    this.api.adjustBillAmount(bill.id, amount).subscribe({
      next: () => {
        this.billError.set(null);
        this.reload();
      },
      error: (error: unknown) => this.billError.set(describeApiError(error)),
    });
  }

  protected payBill(
    bill: BillOccurrence,
    amountInput: HTMLInputElement,
    dateInput: HTMLInputElement,
  ): void {
    this.api.payBill(bill.id, amountInput.value, dateInput.value).subscribe({
      next: () => {
        this.billError.set(null);
        this.billSaved.set(true);
        this.reload();
      },
      error: (error: unknown) => this.billError.set(describeApiError(error)),
    });
  }
}
