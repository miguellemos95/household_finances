import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface NamedReference {
  id: number;
  name: string;
}

export interface Category extends NamedReference {
  is_bill_category: boolean;
  subcategories: NamedReference[];
}

export interface Expense {
  id: number;
  transaction_date: string;
  amount: string;
  category: NamedReference;
  subcategory: NamedReference | null;
}

export interface NewExpense {
  transaction_date: string;
  amount: string;
  category_id: number;
  subcategory_id: number | null;
}

export interface MemberIncome {
  member_id: number;
  member_name: string;
  amount: string | null;
}

export interface NewIncome {
  member_id: number;
  month: string;
  amount: string;
}

export interface MonthlySummary {
  month: string;
  incomes: MemberIncome[];
  total_income: string;
  total_expenses: string;
  balance: string;
  category_budgets: CategoryBudget[];
}

export interface CategoryBudget {
  category: NamedReference;
  month: string;
  limit: string | null;
  spent: string;
  percent: string;
  state: 'unset' | 'under' | 'warning' | 'exceeded';
}

export interface Bill {
  id: number;
  recurrence: 'one_off' | 'monthly';
  first_due_date: string;
  due_day: number | null;
  default_amount: string;
  category: NamedReference;
  subcategory: NamedReference | null;
}

export interface BillOccurrence {
  id: number;
  bill: Bill;
  due_date: string;
  amount: string;
  status: 'pending' | 'overdue' | 'paid';
  paid_amount: string | null;
  paid_date: string | null;
}

export interface NewBill {
  recurrence: 'one_off' | 'monthly';
  due_date: string;
  amount: string;
  category_id: number;
  subcategory_id: number;
}

@Injectable({ providedIn: 'root' })
export class LedgerApi {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  getCategories(): Observable<Category[]> {
    return this.http.get<Category[]>(`${this.baseUrl}/categories`);
  }

  getExpenses(month: string): Observable<Expense[]> {
    return this.http.get<Expense[]>(`${this.baseUrl}/expenses`, { params: { month } });
  }

  getSummary(month: string): Observable<MonthlySummary> {
    return this.http.get<MonthlySummary>(`${this.baseUrl}/summary`, { params: { month } });
  }

  recordExpense(expense: NewExpense): Observable<Expense> {
    return this.http.post<Expense>(`${this.baseUrl}/expenses`, expense);
  }

  recordIncome(income: NewIncome): Observable<unknown> {
    return this.http.post(`${this.baseUrl}/incomes`, income);
  }

  renameMember(memberId: number, name: string): Observable<NamedReference> {
    return this.http.patch<NamedReference>(`${this.baseUrl}/members/${memberId}`, { name });
  }

  setBudget(categoryId: number, month: string, amount: string): Observable<CategoryBudget> {
    return this.http.put<CategoryBudget>(
      `${this.baseUrl}/budgets/${categoryId}`,
      { amount },
      { params: { month } },
    );
  }

  getBills(month: string): Observable<BillOccurrence[]> {
    return this.http.get<BillOccurrence[]>(`${this.baseUrl}/bills`, { params: { month } });
  }

  recordBill(bill: NewBill): Observable<Bill> {
    return this.http.post<Bill>(`${this.baseUrl}/bills`, bill);
  }

  adjustBillAmount(id: number, amount: string): Observable<BillOccurrence> {
    return this.http.put<BillOccurrence>(`${this.baseUrl}/bills/occurrences/${id}/amount`, {
      amount,
    });
  }

  payBill(id: number, paidAmount: string, paidDate: string): Observable<BillOccurrence> {
    return this.http.post<BillOccurrence>(`${this.baseUrl}/bills/occurrences/${id}/pay`, {
      paid_amount: paidAmount,
      paid_date: paidDate,
    });
  }
}
