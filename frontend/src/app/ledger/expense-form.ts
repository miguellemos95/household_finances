import { Component, computed, inject, input, output, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { finalize } from 'rxjs';
import { AMOUNT_HINT, amountValidator, parseAmount } from './amount';
import { describeApiError } from './api-error';
import { Category, Expense, LedgerApi } from './ledger-api';
import { toIsoDate } from './month';

const notInFuture: ValidatorFn = (control) =>
  control.value > toIsoDate(new Date()) ? { future: true } : null;

@Component({
  selector: 'app-expense-form',
  imports: [ReactiveFormsModule],
  templateUrl: './expense-form.html',
  styleUrl: './expense-form.scss',
})
export class ExpenseForm {
  readonly categories = input.required<Category[]>();
  readonly recorded = output<Expense>();

  private readonly api = inject(LedgerApi);

  protected readonly amountHint = AMOUNT_HINT;
  protected readonly today = toIsoDate(new Date());
  protected readonly form = new FormGroup({
    transactionDate: new FormControl(this.today, {
      nonNullable: true,
      validators: [Validators.required, notInFuture],
    }),
    amount: new FormControl('', { nonNullable: true, validators: [amountValidator] }),
    categoryId: new FormControl<number | null>(null, [Validators.required]),
    subcategoryId: new FormControl<number | null>(null),
  });
  private savedValues = this.form.getRawValue();
  private readonly categoryId = toSignal(this.form.controls.categoryId.valueChanges, {
    initialValue: null,
  });
  protected readonly subcategories = computed(
    () =>
      this.categories().find((category) => category.id === this.categoryId())?.subcategories ?? [],
  );
  protected readonly saving = signal(false);
  protected readonly failure = signal<string | null>(null);

  hasUnsavedChanges(): boolean {
    const current = this.form.getRawValue();
    return (
      current.transactionDate !== this.savedValues.transactionDate ||
      current.amount !== this.savedValues.amount ||
      current.categoryId !== this.savedValues.categoryId ||
      current.subcategoryId !== this.savedValues.subcategoryId
    );
  }

  isSaving(): boolean {
    return this.saving();
  }

  resetEntry(): void {
    this.form.reset({
      transactionDate: this.today,
      amount: '',
      categoryId: null,
      subcategoryId: null,
    });
    this.savedValues = this.form.getRawValue();
    this.failure.set(null);
  }

  protected showError(control: AbstractControl): boolean {
    return control.invalid && control.touched;
  }

  protected submit(): void {
    this.failure.set(null);
    const submitted = this.form.getRawValue();
    const { transactionDate, amount, categoryId, subcategoryId } = submitted;
    const parsedAmount = parseAmount(amount);
    if (this.form.invalid || parsedAmount === null || categoryId === null) {
      this.form.markAllAsTouched();
      return;
    }

    this.saving.set(true);
    this.api
      .recordExpense({
        transaction_date: transactionDate,
        amount: parsedAmount,
        category_id: categoryId,
        subcategory_id: subcategoryId,
      })
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (expense) => {
          this.resetEntry();
          this.recorded.emit(expense);
        },
        error: (error: unknown) =>
          this.failure.set(`The expense was not saved. ${describeApiError(error)}`),
      });
  }
}
