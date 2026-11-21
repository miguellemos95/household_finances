import { CurrencyPipe } from '@angular/common';
import { Component, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable, finalize } from 'rxjs';
import { AMOUNT_HINT, amountValidator, parseAmount } from './amount';
import { describeApiError } from './api-error';
import { LedgerApi, MemberIncome } from './ledger-api';
import { formatMonth } from './month';

const NAME_MAX_LENGTH = 50;

@Component({
  selector: 'app-partner-income',
  imports: [CurrencyPipe, ReactiveFormsModule],
  templateUrl: './partner-income.html',
  styleUrl: './partner-income.scss',
})
export class PartnerIncome {
  readonly income = input.required<MemberIncome>();
  readonly month = input.required<string>();
  readonly changed = output<void>();

  private readonly api = inject(LedgerApi);

  protected readonly nameMaxLength = NAME_MAX_LENGTH;
  protected readonly nameForm = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [
        Validators.required,
        Validators.pattern(/\S/),
        Validators.maxLength(NAME_MAX_LENGTH),
      ],
    }),
  });
  protected readonly incomeForm = new FormGroup({
    amount: new FormControl('', { nonNullable: true, validators: [amountValidator] }),
  });
  protected readonly fieldId = computed(() => `partner-${this.income().member_id}`);
  protected readonly monthLabel = computed(() => formatMonth(this.month()));
  protected readonly renaming = signal(false);
  protected readonly saving = signal(false);
  protected readonly failure = signal<string | null>(null);

  hasUnsavedChanges(): boolean {
    return (
      this.incomeForm.getRawValue().amount !== '' ||
      (this.renaming() && this.nameForm.getRawValue().name !== this.income().member_name)
    );
  }

  protected startRenaming(): void {
    this.nameForm.setValue({ name: this.income().member_name });
    this.nameForm.markAsPristine();
    this.failure.set(null);
    this.renaming.set(true);
  }

  protected saveName(): void {
    if (this.nameForm.invalid) {
      this.failure.set(`Enter a name of up to ${NAME_MAX_LENGTH} characters.`);
      return;
    }
    const name = this.nameForm.getRawValue().name.trim();
    this.save(this.api.renameMember(this.income().member_id, name), 'The name was not saved.', () =>
      this.renaming.set(false),
    );
  }

  protected saveIncome(): void {
    const amount = parseAmount(this.incomeForm.getRawValue().amount);
    if (amount === null) {
      this.failure.set(AMOUNT_HINT);
      return;
    }
    const income = { member_id: this.income().member_id, month: this.month(), amount };
    this.save(this.api.recordIncome(income), 'The income was not saved.', () =>
      this.incomeForm.reset(),
    );
  }

  private save(request: Observable<unknown>, failurePrefix: string, onSaved: () => void): void {
    this.failure.set(null);
    this.saving.set(true);
    request.pipe(finalize(() => this.saving.set(false))).subscribe({
      next: () => {
        onSaved();
        this.changed.emit();
      },
      error: (error: unknown) => this.failure.set(`${failurePrefix} ${describeApiError(error)}`),
    });
  }
}
