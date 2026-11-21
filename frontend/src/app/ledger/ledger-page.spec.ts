import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { environment } from '../../environments/environment';
import { BillOccurrence, Category, Expense, MonthlySummary } from './ledger-api';
import { LedgerPage } from './ledger-page';

const api = environment.apiBaseUrl;

const CATEGORIES: Category[] = [
  {
    id: 1,
    name: 'Bills',
    subcategories: [
      { id: 3, name: 'Heating' },
      { id: 4, name: 'Home Internet' },
    ],
  },
  { id: 2, name: 'Groceries', subcategories: [] },
];

const INTERNET: Expense = {
  id: 7,
  transaction_date: '2025-11-03',
  amount: '12.36',
  category: { id: 1, name: 'Bills' },
  subcategory: { id: 4, name: 'Home Internet' },
};

const DATABASE_UNAVAILABLE = {
  detail: { code: 'database_unavailable', message: 'Database is unavailable.' },
};

function summary(overrides: Partial<MonthlySummary> = {}): MonthlySummary {
  return {
    month: '2025-11',
    incomes: [
      { member_id: 1, member_name: 'Azul', amount: '4053.50' },
      { member_id: 2, member_name: 'Pinketa', amount: null },
    ],
    total_income: '4053.50',
    total_expenses: '12.36',
    balance: '4041.14',
    category_budgets: [
      {
        category: { id: 1, name: 'Bills' },
        month: '2025-11',
        limit: '100.00',
        spent: '12.36',
        percent: '12.36',
        state: 'under',
      },
      {
        category: { id: 2, name: 'Groceries' },
        month: '2025-11',
        limit: null,
        spent: '0.00',
        percent: '0.00',
        state: 'unset',
      },
    ],
    ...overrides,
  };
}

describe('LedgerPage', () => {
  let fixture: ComponentFixture<LedgerPage>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(async () => {
    if (!HTMLDialogElement.prototype.showModal) {
      HTMLDialogElement.prototype.showModal = function () {
        this.setAttribute('open', '');
      };
      HTMLDialogElement.prototype.close = function () {
        this.removeAttribute('open');
      };
    }
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2025, 10, 15, 12));
    await TestBed.configureTestingModule({
      imports: [LedgerPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(LedgerPage);
    page = fixture.nativeElement;
    fixture.detectChanges();
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  function flushLedger(
    month = '2025-11',
    monthSummary = summary({ month }),
    expenses: Expense[] = [INTERNET],
    bills: BillOccurrence[] = [],
  ): void {
    http.expectOne(`${api}/categories`).flush(CATEGORIES);
    http.expectOne(`${api}/summary?month=${month}`).flush(monthSummary);
    http.expectOne(`${api}/expenses?month=${month}`).flush(expenses);
    http.expectOne(`${api}/bills?month=${month}`).flush(bills);
    fixture.detectChanges();
  }

  function element<T extends HTMLElement>(selector: string): T {
    const found = page.querySelector<T>(selector);
    if (!found) {
      throw new Error(`No element matches ${selector}`);
    }
    return found;
  }

  function type(selector: string, value: string): void {
    const input = element<HTMLInputElement>(selector);
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  function choose(selector: string, optionIndex: number): void {
    const select = element<HTMLSelectElement>(selector);
    select.selectedIndex = optionIndex;
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  function submitFormOf(selector: string): void {
    element(selector)
      .closest('form')
      ?.dispatchEvent(new Event('submit', { cancelable: true }));
    fixture.detectChanges();
  }

  function clickButton(label: string): void {
    const button = Array.from(page.querySelectorAll('button')).find(
      (candidate) => candidate.textContent?.trim() === label,
    );
    if (!button) {
      throw new Error(`No button labelled ${label}`);
    }
    button.click();
    fixture.detectChanges();
  }

  function clickDialogButton(titleId: string, label: string): void {
    const dialog = element<HTMLElement>(`#${titleId}`).closest('dialog');
    const button = Array.from(dialog?.querySelectorAll('button') ?? []).find(
      (candidate) => candidate.textContent?.trim() === label,
    );
    if (!button) throw new Error(`No dialog button labelled ${label}`);
    button.click();
    fixture.detectChanges();
  }

  function fillExpense(date: string, amount: string): void {
    type('#expense-date', date);
    type('#expense-amount', amount);
    choose('#expense-category', 1);
    choose('#expense-subcategory', 2);
  }

  it('switches sections without losing drafts and starts dialogs closed', () => {
    flushLedger();
    const expenses = element<HTMLElement>('[aria-labelledby="expenses-title"]').parentElement!;
    const bills = element<HTMLElement>('[aria-labelledby="bills-title"]').parentElement!;
    expect(expenses.hidden).toBe(true);
    expect(bills.hidden).toBe(true);
    expect(element<HTMLElement>('#expense-dialog-title').closest('dialog')?.open).toBe(false);
    expect(element<HTMLElement>('#bill-dialog-title').closest('dialog')?.open).toBe(false);

    type('#partner-2-amount', '42.00');
    clickButton('Bills');
    clickButton('Expenses');
    expect(expenses.hidden).toBe(false);
    expect(bills.hidden).toBe(true);
    expect(element<HTMLInputElement>('#partner-2-amount').value).toBe('42.00');
    expect(element<HTMLButtonElement>('.tab[aria-pressed="true"]').textContent?.trim()).toBe(
      'Expenses',
    );
  });

  it('closes an edited expense on Escape without confirmation and resets the draft', () => {
    flushLedger();
    clickButton('Expenses');
    clickButton('Add expense');
    const dialog = element<HTMLElement>('#expense-dialog-title').closest('dialog')!;
    expect(dialog.open).toBe(true);
    type('#expense-amount', '12.00');
    const confirm = vi.spyOn(window, 'confirm');
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    dialog.dispatchEvent(escape);
    fixture.detectChanges();
    expect(escape.defaultPrevented).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
    expect(dialog.open).toBe(false);
    clickButton('Add expense');
    expect(element<HTMLInputElement>('#expense-amount').value).toBe('');
    confirm.mockRestore();
  });

  it.each([
    ['Expenses', 'Add expense', '#expense-dialog-title', '#expense-amount'],
    ['Bills', 'Add bill', '#bill-dialog-title', '#bill-amount'],
  ])(
    'requests a leave-page warning only while %s dialog has edits',
    (section, button, title, input) => {
      flushLedger();
      clickButton(section);
      clickButton(button);
      let event = new Event('beforeunload', { cancelable: true });
      window.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(false);

      type(input, '12.00');
      event = new Event('beforeunload', { cancelable: true });
      window.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(true);

      type(input, '');
      event = new Event('beforeunload', { cancelable: true });
      window.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(false);
      type(input, '12.00');
      clickDialogButton(title.slice(1), 'Close');
      expect(element<HTMLElement>(title).closest('dialog')?.open).toBe(false);
      expect(element<HTMLInputElement>(input).value).toBe('');
      event = new Event('beforeunload', { cancelable: true });
      window.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(false);
    },
  );

  it('does not request a leave-page warning for edits outside dialogs', () => {
    flushLedger();
    type('#partner-2-amount', '100.00');
    type('#budget-1', '120.00');
    clickButton('Expenses');
    clickButton('Add expense');
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });

  it('keeps expense errors in the dialog and closes with a fresh form after saving', () => {
    flushLedger();
    clickButton('Expenses');
    clickButton('Add expense');
    const dialog = element<HTMLElement>('#expense-dialog-title').closest('dialog')!;
    fillExpense('2025-11-10', '12.36');
    submitFormOf('#expense-amount');
    http
      .expectOne(`${api}/expenses`)
      .flush(DATABASE_UNAVAILABLE, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();
    expect(dialog.open).toBe(true);
    expect(dialog.textContent).toContain('Database is unavailable.');
    expect(element<HTMLInputElement>('#expense-amount').value).toBe('12.36');
    submitFormOf('#expense-amount');
    http.expectOne(`${api}/expenses`).flush({ ...INTERNET, id: 8 });
    flushLedger();
    expect(dialog.open).toBe(false);
    expect(element<HTMLElement>('[aria-labelledby="expenses-title"]').textContent).toContain(
      'Expense recorded.',
    );
    clickButton('Add expense');
    expect(element<HTMLInputElement>('#expense-amount').value).toBe('');
    expect(element<HTMLSelectElement>('#expense-category').selectedIndex).toBe(0);
  });

  it('saves a bill and resets it after success', () => {
    flushLedger();
    clickButton('Bills');
    clickButton('Add bill');
    const dialog = element<HTMLElement>('#bill-dialog-title').closest('dialog')!;
    type('#bill-due-date', '2025-11-20');
    type('#bill-amount', '45.00');
    choose('#bill-category', 1);
    submitFormOf('#bill-amount');
    http.expectOne(`${api}/bills`).flush({ id: 1 });
    flushLedger();
    expect(dialog.open).toBe(false);
    clickButton('Add bill');
    expect(element<HTMLInputElement>('#bill-amount').value).toBe('');
    expect(element<HTMLSelectElement>('#bill-category').value).toBe('0');
  });

  it.each([
    ['expense', () => type('#expense-amount', '12.00')],
    ['income', () => type('#partner-2-amount', '100.00')],
    [
      'name',
      () => {
        clickButton('Rename');
        type('#partner-1-name', 'New name');
      },
    ],
    ['bill', () => type('#bill-amount', '20.00')],
    ['bill due date', () => type('#bill-due-date', '2025-11-25')],
    ['bill recurrence', () => choose('#bill-recurrence', 1)],
    ['bill category', () => choose('#bill-category', 1)],
    ['budget', () => type('#budget-1', '120.00')],
  ])('warns before discarding an unsaved %s edit and honors cancel', (_name, edit) => {
    flushLedger();
    edit();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);

    clickButton('Next');
    expect(confirm).toHaveBeenCalledOnce();
    expect(page.textContent).toContain('November 2025');
    http.expectNone(`${api}/summary?month=2025-12`);
    confirm.mockRestore();
  });

  it('restores the month selector on cancel and discards drafts on confirmation', () => {
    flushLedger();
    clickButton('Expenses');
    type('#expense-amount', '12.00');
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const input = element<HTMLInputElement>('#ledger-month');
    input.value = '2025-12';
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(input.value).toBe('2025-11');
    expect(element<HTMLInputElement>('#expense-amount').value).toBe('12.00');

    confirm.mockReturnValue(true);
    clickButton('Next');
    flushLedger('2025-12', summary({ month: '2025-12' }), []);
    expect(element<HTMLInputElement>('#expense-amount').value).toBe('');
    expect(element<HTMLButtonElement>('.tab[aria-pressed="true"]').textContent?.trim()).toBe(
      'Expenses',
    );
    confirm.mockRestore();
  });

  it('does not warn when a budget amount is unchanged apart from formatting', () => {
    flushLedger();
    type('#budget-1', '100,0');
    const confirm = vi.spyOn(window, 'confirm');
    clickButton('Next');
    expect(confirm).not.toHaveBeenCalled();
    flushLedger('2025-12', summary({ month: '2025-12' }), []);
    confirm.mockRestore();
  });

  it('restores the selected month when the month input is cleared', () => {
    flushLedger();
    const input = element<HTMLInputElement>('#ledger-month');
    input.value = '';
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(input.value).toBe('2025-11');
    http.expectNone(`${api}/summary?month=`);
  });

  it.each(['amount', 'date'])('warns about unsaved bill payment %s edits', (field) => {
    const bill: BillOccurrence = {
      id: 9,
      bill: {
        id: 2,
        recurrence: 'one_off',
        first_due_date: '2025-11-20',
        due_day: null,
        default_amount: '45.00',
        category: { id: 1, name: 'Bills' },
        subcategory: null,
      },
      due_date: '2025-11-20',
      amount: '45.00',
      status: 'pending',
      paid_amount: null,
      paid_date: null,
    };
    flushLedger('2025-11', summary(), [INTERNET], [bill]);
    type(
      field === 'amount' ? '#bill-occurrence-9' : '[aria-label="Paid date for bill 9"]',
      field === 'amount' ? '50.00' : '2025-11-14',
    );
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    clickButton('Next');
    expect(confirm).toHaveBeenCalledOnce();
    expect(page.textContent).toContain('November 2025');
    confirm.mockRestore();
  });

  it('should show the current month summary, partner incomes and expenses', () => {
    flushLedger('2025-11', summary({ total_income: '6078.50', balance: '6066.14' }));

    const text = page.textContent ?? '';
    expect(text).toContain('November 2025');
    expect(text).toContain('€6,078.50');
    expect(text).toContain('€12.36');
    expect(text).toContain('€6,066.14');
    expect(text).toContain('Azul');
    expect(text).toContain('€4,053.50');
    expect(text).toContain('Pinketa');
    expect(text).toContain('Home Internet');
    expect(text).toContain('3 Nov 2025');
  });

  it('should load the selected month when navigating', () => {
    flushLedger();

    clickButton('Next');
    expect(page.querySelector('.summary')).toBeNull();
    expect(page.textContent).not.toContain('€4,041.14');
    expect(page.textContent).toContain('Loading the ledger…');

    flushLedger(
      '2025-12',
      summary({ month: '2025-12', total_expenses: '0.00', balance: '4053.50' }),
      [],
    );

    expect(page.textContent).toContain('December 2025');
    expect(page.textContent).toContain('No expenses recorded for December 2025.');
  });

  it('should report a failed load, hide stale figures and retry on request', () => {
    http.expectOne(`${api}/categories`).flush(CATEGORIES);
    http.expectOne(`${api}/summary?month=2025-11`).error(new ProgressEvent('error'));
    expect(http.expectOne(`${api}/expenses?month=2025-11`).cancelled).toBe(true);
    expect(http.expectOne(`${api}/bills?month=2025-11`).cancelled).toBe(true);
    fixture.detectChanges();

    expect(page.textContent).toContain(
      'The ledger could not be loaded. The API could not be reached.',
    );
    expect(page.querySelector('.summary')).toBeNull();

    clickButton('Try again');
    flushLedger();

    expect(page.querySelector('[role="alert"]')).toBeNull();
    expect(page.textContent).toContain('€4,041.14');
  });

  it('should record an expense as decimal text and refresh the month', () => {
    flushLedger();

    fillExpense('2025-11-10', '12.36');
    submitFormOf('#expense-amount');

    const request = http.expectOne(`${api}/expenses`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      transaction_date: '2025-11-10',
      amount: '12.36',
      category_id: 1,
      subcategory_id: 4,
    });
    request.flush({ ...INTERNET, id: 8, transaction_date: '2025-11-10' });
    flushLedger('2025-11', summary({ total_expenses: '24.72', balance: '4028.78' }));

    expect(page.textContent).toContain('Expense recorded.');
    expect(page.textContent).toContain('€24.72');
    expect(element<HTMLInputElement>('#expense-amount').value).toBe('');
  });

  it('disables expense entry while its save is in flight', () => {
    flushLedger();
    fillExpense('2025-11-10', '12.36');
    submitFormOf('#expense-amount');
    const request = http.expectOne(`${api}/expenses`);
    fixture.detectChanges();
    expect(element<HTMLFieldSetElement>('app-expense-form fieldset').disabled).toBe(true);
    request.flush({ ...INTERNET, id: 8, transaction_date: '2025-11-10' });
    flushLedger();
    expect(element<HTMLInputElement>('#expense-amount').value).toBe('');
  });

  it('should show the month of a recorded expense dated in another month', () => {
    flushLedger();

    fillExpense('2025-10-31', '5.00');
    submitFormOf('#expense-amount');
    http
      .expectOne(`${api}/expenses`)
      .flush({ ...INTERNET, id: 9, transaction_date: '2025-10-31', amount: '5.00' });
    flushLedger('2025-10');

    expect(page.textContent).toContain('October 2025');
  });

  it('should not send an incomplete expense', () => {
    flushLedger();

    type('#expense-amount', '12,50');
    submitFormOf('#expense-amount');

    http.expectNone(`${api}/expenses`);
    expect(page.textContent).toContain('Enter an amount greater than 0');
    expect(page.textContent).toContain('Choose a category.');
  });

  it('should report a failed expense write without confirming or refreshing', () => {
    flushLedger();

    fillExpense('2025-11-10', '12.36');
    submitFormOf('#expense-amount');
    http
      .expectOne(`${api}/expenses`)
      .flush(DATABASE_UNAVAILABLE, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();

    expect(page.textContent).toContain('The expense was not saved. Database is unavailable.');
    expect(page.textContent).not.toContain('Expense recorded.');
    expect(element<HTMLInputElement>('#expense-amount').value).toBe('12.36');
    http.expectNone(`${api}/summary?month=2025-11`);
  });

  it('should record income for a partner and refresh the month', () => {
    flushLedger();

    type('#partner-2-amount', '2025.00');
    submitFormOf('#partner-2-amount');

    const request = http.expectOne(`${api}/incomes`);
    expect(request.request.body).toEqual({ member_id: 2, month: '2025-11', amount: '2025.00' });
    request.flush({ id: 1, member_id: 2, month: '2025-11', amount: '2025.00' });
    flushLedger(
      '2025-11',
      summary({
        incomes: [
          { member_id: 1, member_name: 'Azul', amount: '4053.50' },
          { member_id: 2, member_name: 'Pinketa', amount: '2025.00' },
        ],
        total_income: '6078.50',
        balance: '6066.14',
      }),
    );

    expect(page.textContent).toContain('€2,025.00');
    expect(page.textContent).toContain('€6,078.50');
    expect(page.querySelector('#partner-2-amount')).toBeNull();
  });

  it('should report an income that is already recorded', () => {
    flushLedger();

    type('#partner-2-amount', '2025.00');
    submitFormOf('#partner-2-amount');
    http.expectOne(`${api}/incomes`).flush(
      {
        detail: {
          code: 'conflict',
          message: 'Income for this member and month is already recorded.',
        },
      },
      { status: 409, statusText: 'Conflict' },
    );
    fixture.detectChanges();

    expect(page.textContent).toContain(
      'The income was not saved. Income for this member and month is already recorded.',
    );
  });

  it('should not send an invalid income amount', () => {
    flushLedger();

    type('#partner-2-amount', '0');
    submitFormOf('#partner-2-amount');

    http.expectNone(`${api}/incomes`);
    expect(page.textContent).toContain('Enter an amount greater than 0');
  });

  it('should set a monthly budget and show warning and exceeded states', () => {
    flushLedger();

    type('#budget-1', '100.00');
    submitFormOf('#budget-1');
    const request = http.expectOne(`${api}/budgets/1?month=2025-11`);
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ amount: '100.00' });
    request.flush({
      category: { id: 1, name: 'Bills' },
      month: '2025-11',
      limit: '100.00',
      spent: '80.00',
      percent: '80.00',
      state: 'warning',
    });
    flushLedger(
      '2025-11',
      summary({
        category_budgets: [
          {
            category: { id: 1, name: 'Bills' },
            month: '2025-11',
            limit: '100.00',
            spent: '80.00',
            percent: '80.00',
            state: 'warning',
          },
          {
            category: { id: 2, name: 'Groceries' },
            month: '2025-11',
            limit: '50.00',
            spent: '60.00',
            percent: '120.00',
            state: 'exceeded',
          },
        ],
      }),
    );

    expect(page.textContent).toContain('Budget saved.');
    expect(page.textContent).toContain('Warning');
    expect(page.textContent).toContain('Over budget');
    expect(page.textContent).toContain('80.00% used');
    expect(page.textContent).toContain('120.00% used');
  });

  it('should not send an invalid budget amount', () => {
    flushLedger();

    type('#budget-1', '0');
    submitFormOf('#budget-1');

    http.expectNone(`${api}/budgets/1?month=2025-11`);
    expect(page.textContent).toContain('Enter a budget amount greater than 0');
  });

  it('keeps a failed budget edit and its error visible in Budgets', () => {
    flushLedger();
    clickButton('Budgets');
    type('#budget-1', '120.00');
    submitFormOf('#budget-1');
    http
      .expectOne(`${api}/budgets/1?month=2025-11`)
      .flush(DATABASE_UNAVAILABLE, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();
    expect(element<HTMLElement>('.budget-panel').hidden).toBe(false);
    expect(element<HTMLElement>('.budget-panel [role="alert"]').textContent).toContain(
      'Database is unavailable.',
    );
    expect(element<HTMLInputElement>('#budget-1').value).toBe('120.00');
  });

  it('should create a bill and refresh the ledger', () => {
    flushLedger();

    choose('#bill-recurrence', 1);
    type('#bill-due-date', '2025-12-20');
    type('#bill-amount', '45.00');
    choose('#bill-category', 1);
    submitFormOf('#bill-amount');

    const request = http.expectOne(`${api}/bills`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      recurrence: 'monthly',
      due_date: '2025-12-20',
      amount: '45.00',
      category_id: 1,
      subcategory_id: null,
    });

    request.flush({
      id: 1,
      recurrence: 'monthly',
      first_due_date: '2025-12-20',
      due_day: 20,
      default_amount: '45.00',
      category: { id: 1, name: 'Bills' },
      subcategory: null,
    });
    flushLedger();

    expect(page.textContent).toContain('Bill saved or marked paid.');
    const confirm = vi.spyOn(window, 'confirm');
    clickButton('Next');
    expect(confirm).not.toHaveBeenCalled();
    flushLedger('2025-12', summary({ month: '2025-12' }), []);
    confirm.mockRestore();
  });

  it('keeps a failed bill edit and its error visible in Bills', () => {
    flushLedger();
    clickButton('Bills');
    clickButton('Add bill');
    type('#bill-due-date', '2025-11-20');
    type('#bill-amount', '45.00');
    choose('#bill-category', 1);
    submitFormOf('#bill-amount');
    http
      .expectOne(`${api}/bills`)
      .flush(DATABASE_UNAVAILABLE, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();
    expect(element<HTMLElement>('.bill-panel').parentElement?.hidden).toBe(false);
    expect(element<HTMLElement>('#bill-dialog-title').closest('dialog')?.open).toBe(true);
    expect(element<HTMLElement>('.bill-panel [role="alert"]').textContent).toContain(
      'Database is unavailable.',
    );
    expect(element<HTMLInputElement>('#bill-amount').value).toBe('45.00');
  });

  it('should send a selected bill subcategory and clear it when category changes', () => {
    flushLedger();
    type('#bill-due-date', '2025-11-20');
    type('#bill-amount', '45.00');
    choose('#bill-category', 1);
    choose('#bill-subcategory', 2);
    choose('#bill-category', 2);
    expect(page.querySelector('#bill-subcategory')).toBeNull();
    choose('#bill-category', 1);
    expect(element<HTMLSelectElement>('#bill-subcategory').value).toBe('');
    choose('#bill-subcategory', 2);
    submitFormOf('#bill-amount');
    const request = http.expectOne(`${api}/bills`);
    expect(request.request.body.subcategory_id).toBe(4);
    request.flush({ id: 1 });
    flushLedger();
  });

  it('clears a bill subcategory when the dialog is closed', () => {
    flushLedger();
    clickButton('Bills');
    clickButton('Add bill');
    type('#bill-due-date', '2025-11-20');
    type('#bill-amount', '45.00');
    choose('#bill-category', 1);
    choose('#bill-subcategory', 1);
    clickDialogButton('bill-dialog-title', 'Close');
    expect(element<HTMLElement>('#bill-dialog-title').closest('dialog')!.open).toBe(false);
    expect(element<HTMLInputElement>('#bill-amount').value).toBe('');
    expect(page.querySelector('#bill-subcategory')).toBeNull();
  });

  it('should mark a pending bill paid and refresh totals', () => {
    const bill: BillOccurrence = {
      id: 9,
      bill: {
        id: 2,
        recurrence: 'one_off',
        first_due_date: '2025-11-20',
        due_day: null,
        default_amount: '45.00',
        category: { id: 1, name: 'Bills' },
        subcategory: null,
      },
      due_date: '2025-11-20',
      amount: '45.00',
      status: 'pending',
      paid_amount: null,
      paid_date: null,
    };
    flushLedger('2025-11', summary(), [INTERNET], [bill]);

    clickButton('Mark paid');
    const request = http.expectOne(`${api}/bills/occurrences/9/pay`);
    expect(request.request.body).toEqual({
      paid_amount: '45.00',
      paid_date: '2025-11-15',
    });
    request.flush({
      ...bill,
      status: 'paid',
      paid_amount: '45.00',
      paid_date: '2025-11-15',
    });
    flushLedger('2025-11', summary({ total_expenses: '57.36', balance: '3996.14' }));

    expect(page.textContent).toContain('Bill saved or marked paid.');
  });

  it('should report a failed payment without confirming or refreshing', () => {
    const bill: BillOccurrence = {
      id: 9,
      bill: {
        id: 2,
        recurrence: 'one_off',
        first_due_date: '2025-11-10',
        due_day: null,
        default_amount: '45.00',
        category: { id: 1, name: 'Bills' },
        subcategory: null,
      },
      due_date: '2025-11-10',
      amount: '45.00',
      status: 'overdue',
      paid_amount: null,
      paid_date: null,
    };
    flushLedger('2025-11', summary(), [INTERNET], [bill]);
    clickButton('Mark paid');
    http
      .expectOne(`${api}/bills/occurrences/9/pay`)
      .flush(DATABASE_UNAVAILABLE, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();

    expect(page.textContent).toContain('The bill was not saved. Database is unavailable.');
    expect(page.textContent).not.toContain('Bill saved or marked paid.');
    expect(page.textContent).toContain('overdue');
    http.expectNone(`${api}/summary?month=2025-11`);
  });

  it('should rename a partner and refresh the month', () => {
    flushLedger();

    clickButton('Rename');
    expect(element<HTMLInputElement>('#partner-1-name').value).toBe('Azul');
    type('#partner-1-name', '  Miguel ');
    submitFormOf('#partner-1-name');

    const request = http.expectOne(`${api}/members/1`);
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ name: 'Miguel' });
    request.flush({ id: 1, name: 'Miguel' });
    flushLedger(
      '2025-11',
      summary({
        incomes: [
          { member_id: 1, member_name: 'Miguel', amount: '4053.50' },
          { member_id: 2, member_name: 'Pinketa', amount: null },
        ],
      }),
    );

    expect(page.textContent).toContain('Miguel');
    expect(page.querySelector('#partner-1-name')).toBeNull();
  });

  it('should report a rejected partner name and keep the old one', () => {
    flushLedger();

    clickButton('Rename');
    type('#partner-1-name', 'Miguel');
    submitFormOf('#partner-1-name');
    http.expectOne(`${api}/members/1`).flush(
      {
        detail: {
          code: 'invalid_input',
          message: 'The request contains invalid values.',
          errors: [{ field: 'name', message: 'String should have at least 1 character' }],
        },
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    fixture.detectChanges();

    expect(page.textContent).toContain(
      'The name was not saved. The request contains invalid values. ' +
        'name: String should have at least 1 character',
    );
    clickButton('Cancel');
    expect(page.textContent).toContain('Azul');
  });
});
