import { CurrencyPipe, DatePipe } from '@angular/common';
import {
  Component,
  ElementRef,
  HostListener,
  OnInit,
  QueryList,
  ViewChild,
  ViewChildren,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, catchError, finalize, forkJoin, map, of, switchMap } from 'rxjs';
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

type LedgerSection = 'overview' | 'expenses' | 'bills' | 'budgets';
type EntryDialog = 'expense' | 'bill';

interface BillDraft {
  recurrence: string;
  dueDate: string;
  amount: string;
  category: string;
  subcategory: string;
}

function sameAmount(first: string, second: string): boolean {
  const normalize = (value: string): string => {
    const text = value.trim().replace(',', '.');
    if (!/^\d+(?:\.\d{1,2})?$/.test(text)) return text;
    const [whole, fraction = ''] = text.split('.');
    return `${whole.replace(/^0+(?=\d)/, '')}.${fraction.padEnd(2, '0')}`;
  };
  return normalize(first) === normalize(second);
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
  @ViewChild(ExpenseForm) private expenseForm?: ExpenseForm;
  @ViewChild('expenseDialog') private expenseDialog?: ElementRef<HTMLDialogElement>;
  @ViewChild('billDialog') private billDialog?: ElementRef<HTMLDialogElement>;
  @ViewChild('billCreateForm') private billCreateForm?: ElementRef<HTMLFormElement>;
  @ViewChildren(PartnerIncome) private partnerIncomes!: QueryList<PartnerIncome>;
  @ViewChild('billRecurrence') private billRecurrence?: ElementRef<HTMLSelectElement>;
  @ViewChild('billDueDate') private billDueDate?: ElementRef<HTMLInputElement>;
  @ViewChild('billAmount') private billAmount?: ElementRef<HTMLInputElement>;
  @ViewChild('billCategory') private billCategory?: ElementRef<HTMLSelectElement>;
  @ViewChild('billSubcategory') private billSubcategory?: ElementRef<HTMLSelectElement>;
  @ViewChildren('budgetInput') private budgetInputs!: QueryList<ElementRef<HTMLInputElement>>;
  @ViewChildren('billAmountInput') private billAmountInputs!: QueryList<
    ElementRef<HTMLInputElement>
  >;
  @ViewChildren('billPaidDate') private billPaidDates!: QueryList<ElementRef<HTMLInputElement>>;
  private billDraftBaseline: BillDraft = this.emptyBillDraft();

  protected readonly section = signal<LedgerSection>('overview');
  protected readonly expenseSaved = signal(false);
  protected readonly billSaving = signal(false);
  protected readonly sections: { id: LedgerSection; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'expenses', label: 'Expenses' },
    { id: 'bills', label: 'Bills' },
    { id: 'budgets', label: 'Budgets' },
  ];
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
  protected readonly billCategoryId = signal<number | null>(null);
  protected readonly billSubcategoryId = signal<number | null>(null);
  protected readonly billSubcategories = computed(
    () =>
      this.visibleLedger()?.categories.find((category) => category.id === this.billCategoryId())
        ?.subcategories ?? [],
  );
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

  @HostListener('window:beforeunload', ['$event'])
  protected beforeUnload(event: BeforeUnloadEvent): void {
    const expenseChanged =
      this.expenseDialog?.nativeElement.open && this.expenseForm?.hasUnsavedChanges();
    const billChanged = this.billDialog?.nativeElement.open && this.billDraftChanged();
    if (expenseChanged || billChanged) {
      event.preventDefault();
      event.returnValue = ' ';
    }
  }

  protected reload(): void {
    this.loads.next(this.month());
  }

  protected selectMonth(month: string, input?: HTMLInputElement): void {
    if (!isMonth(month)) {
      if (input) input.value = this.month();
      return;
    }
    if (
      month !== this.month() &&
      this.hasUnsavedChanges() &&
      !window.confirm('You have unsaved changes. Discard them and change month?')
    ) {
      if (input) input.value = this.month();
      return;
    }
    if (month !== this.month()) {
      this.expenseSaved.set(false);
      this.billDraftBaseline = this.emptyBillDraft();
      this.billCategoryId.set(null);
      this.billSubcategoryId.set(null);
    }
    this.month.set(month);
    this.reload();
  }

  protected moveMonth(offset: number): void {
    this.selectMonth(shiftMonth(this.month(), offset));
  }

  protected showExpenseMonth(expense: Expense): void {
    this.expenseDialog?.nativeElement.close();
    this.selectMonth(expense.transaction_date.slice(0, 7));
    this.expenseSaved.set(true);
  }

  protected openDialog(kind: EntryDialog): void {
    if (kind === 'expense') {
      this.expenseSaved.set(false);
      this.expenseDialog?.nativeElement.showModal();
    } else {
      this.billSaved.set(false);
      this.billError.set(null);
      this.billDialog?.nativeElement.showModal();
    }
  }

  protected requestCloseDialog(kind: EntryDialog, event?: Event): void {
    event?.preventDefault();
    if (kind === 'expense' ? this.expenseForm?.isSaving() : this.billSaving()) return;
    if (kind === 'expense') {
      this.expenseForm?.resetEntry();
      this.expenseDialog?.nativeElement.close();
    } else {
      this.resetBillEntry();
      this.billDialog?.nativeElement.close();
    }
  }

  protected expenseIsSaving(): boolean {
    return this.expenseForm?.isSaving() ?? false;
  }

  private emptyBillDraft(): BillDraft {
    return { recurrence: 'one_off', dueDate: '', amount: '', category: '0', subcategory: '' };
  }

  private currentBillDraft(): BillDraft {
    return {
      recurrence: this.billRecurrence?.nativeElement.value ?? 'one_off',
      dueDate: this.billDueDate?.nativeElement.value ?? '',
      amount: this.billAmount?.nativeElement.value ?? '',
      category: this.billCategory?.nativeElement.value ?? '0',
      subcategory: this.billSubcategory?.nativeElement.value ?? '',
    };
  }

  private resetBillEntry(): void {
    this.billCreateForm?.nativeElement.reset();
    this.billCategoryId.set(null);
    this.billSubcategoryId.set(null);
    this.billDraftBaseline = this.emptyBillDraft();
    this.billError.set(null);
  }

  private billDraftChanged(): boolean {
    const bill = this.currentBillDraft();
    return (
      bill.recurrence !== this.billDraftBaseline.recurrence ||
      bill.dueDate !== this.billDraftBaseline.dueDate ||
      bill.amount !== this.billDraftBaseline.amount ||
      bill.category !== this.billDraftBaseline.category ||
      bill.subcategory !== this.billDraftBaseline.subcategory
    );
  }

  private hasUnsavedChanges(): boolean {
    const ledger = this.visibleLedger();
    if (!ledger) return false;
    if (
      this.expenseForm?.hasUnsavedChanges() ||
      this.partnerIncomes.some((partner) => partner.hasUnsavedChanges())
    ) {
      return true;
    }
    if (this.billDraftChanged()) return true;
    return (
      this.budgetInputs.some(({ nativeElement }) => {
        const budget = ledger.summary.category_budgets.find(
          (item) => `budget-${item.category.id}` === nativeElement.id,
        );
        return budget !== undefined && !sameAmount(nativeElement.value, budget.limit ?? '');
      }) ||
      this.billAmountInputs.some(({ nativeElement }) => {
        const occurrence = ledger.bills.find(
          (item) => `bill-occurrence-${item.id}` === nativeElement.id,
        );
        return occurrence !== undefined && !sameAmount(nativeElement.value, occurrence.amount);
      }) ||
      this.billPaidDates.some(({ nativeElement }) => nativeElement.value !== this.today)
    );
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

  protected selectBillCategory(value: string): void {
    this.billCategoryId.set(Number(value) || null);
    this.billSubcategoryId.set(null);
  }

  protected selectBillSubcategory(value: string): void {
    this.billSubcategoryId.set(Number(value) || null);
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
    this.billSaving.set(true);
    this.api
      .recordBill({
        recurrence: recurrence.value as 'one_off' | 'monthly',
        due_date: dueDate.value,
        amount: parsedAmount,
        category_id: categoryId,
        subcategory_id: this.billSubcategoryId(),
      })
      .pipe(finalize(() => this.billSaving.set(false)))
      .subscribe({
        next: () => {
          this.resetBillEntry();
          this.billDialog?.nativeElement.close();
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
    this.billSaved.set(false);
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
    this.billSaved.set(false);
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
