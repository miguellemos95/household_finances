import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { environment } from '../../environments/environment';
import { Category, Expense, MonthlySummary } from './ledger-api';
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
  ): void {
    http.expectOne(`${api}/categories`).flush(CATEGORIES);
    http.expectOne(`${api}/summary?month=${month}`).flush(monthSummary);
    http.expectOne(`${api}/expenses?month=${month}`).flush(expenses);
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

  function fillExpense(date: string, amount: string): void {
    type('#expense-date', date);
    type('#expense-amount', amount);
    choose('#expense-category', 1);
    choose('#expense-subcategory', 2);
  }

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
