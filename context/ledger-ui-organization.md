# Ledger UI organization

## Status

PR [#17](https://github.com/miguellemos95/household_finances/pull/17) merged;
issue #15 closed after post-merge verification.

**Ticket:** [#15](https://github.com/miguellemos95/household_finances/issues/15).

## Objective and confirmed requirements

- Reduce the density of the monthly ledger while retaining its existing visual design.
- Organize the interface into four tabs: Overview, Expenses, Bills, and Budgets.
- Overview: monthly summary figures and partner income.
- Expenses: expense list and an add-expense form.
- Bills: bill list, payment actions, and the add-bill form.
- Budgets: category budget cards and limits.
- Place add-expense and add-bill buttons in their respective sections; each
  opens a modal dialog.
- Modal dialogs block interaction with the page behind them. Closing a dialog
  discards its unsaved entries without a confirmation. If saving fails
  validation or the API request fails, keep the dialog open and show the error.
  Close on successful save and start a fresh entry when reopened.
- Warn with the browser's standard leave-page confirmation when refreshing or
  navigating away while a pop-up contains unsaved entries. Do not warn for
  other sections' unsaved edits when leaving the browser page.
- Keep the month selector visible across tabs.
- Keep other unsaved entries when switching tabs. While an entry dialog is open,
  the tabs and month selector cannot be used. Before changing month, warn about
  other unsaved edits; cancellation keeps the current month and edits, while
  confirmation discards them and changes month.
- Start on Overview after refresh; do not encode the active tab in the URL.
- Provide keyboard-accessible navigation, visible focus, and an accessible
  indication of the active section.

## Design

- Preserve existing financial behavior and error handling.
- The Angular ledger retains each section in the view while hiding inactive
  sections, so switching sections does not destroy its forms.
- Modal dialogs contain the entry forms and prevent interaction with the
  underlying page. Closing a dialog discards its draft immediately.
- Use the browser's `beforeunload` event to request a warning only when an open
  entry dialog has unsaved edits. Browser policy controls the wording and may
  suppress the warning, including when there has been no user activation.
- Compare editable values with their saved or initial values before a month
  change; use a confirmation dialog when edits would be discarded.
- The active section is local UI state. The API, backend, and data model do not
  change.

## Acceptance criteria

- **AC1:** The four tabs make the existing ledger sections available without displaying all
  sections at once.
- **AC2:** Add-expense and add-bill buttons open modal dialogs; closing discards
  unsaved entries without confirmation. Successful saves close the dialog and
  reopening starts a fresh entry; failed saves retain the form and show errors.
- **AC3:** The existing visual style and financial operations are preserved.
- **AC4:** The selected month is visible and consistent across the ledger sections.
- **AC5:** Switching tabs retains unsaved edits; changing month warns before discarding
  unsaved edits, and canceling leaves the month and edits unchanged.
- **AC6:** Refresh starts on Overview; section navigation is keyboard accessible.
- **AC7:** Loading, success, and error states remain available where relevant.
- **AC8:** Refreshing or navigating away with unsaved edits in an open dialog
  requests a browser leave-page warning; other edits do not trigger this warning.

Verification must cover the agreed behaviors and existing financial operations.

## Open questions

- None for the agreed scope.

## Ticket draft

**Title:** Organize the monthly ledger into tabs

**Description:** Reduce the density of the monthly ledger while preserving its
visual design and existing functionality. Introduce Overview, Expenses, Bills,
and Budgets tabs with the section placement described above. Put the add-expense
and add-bill forms in modal dialogs with the agreed close and leave-page behavior.
Keep month navigation visible, retain other edits across tabs, and warn before
changing month with unsaved edits.
Start on Overview after refresh and support keyboard-accessible navigation.
Verify existing operations and loading and error handling with focused tests and
the consolidated test and error-handling table.

**Registered ticket ID:** [#15](https://github.com/miguellemos95/household_finances/issues/15).

## Test and error-handling evidence

Executed 2026-11-21 from `frontend/`. The Angular tests use mock HTTP responses;
the browser checks used a mock API, not the live database. Infrastructure
failover is out of scope.

| Test ID | Requirement / acceptance criterion | Level | Scenario / failure condition | Expected outcome / recovery | Actual outcome | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UI-01 | AC1, AC5 | Angular | Switch sections with an income draft | One active section; dialogs initially closed; draft retained | Matched | Passed | `ledger-page.spec.ts`: `switches sections without losing drafts and starts dialogs closed` |
| UI-02 | AC2, AC7 | Angular | Close edited dialogs; validation failure, API failure, and success | Close discards without confirmation; retain failed entries; close and reset on success | Matched for expense and bill cases | Passed | `ledger-page.spec.ts`: dialog, invalid-entry and failed-save cases |
| UI-03 | AC4, AC5 | Angular | Change month with edits to income, name, bill payment and budget fields; clear the month input | Warn; cancel preserves entries; confirm discards; invalid month restores the selector | Matched; equivalent budget formatting does not trigger a false warning | Passed | `ledger-page.spec.ts`: warning, formatting and month-selector cases |
| UI-04 | AC1, AC2, AC4, AC6 | Browser | Keyboard navigation, modal background blocking, Escape, refresh and 390px viewport | Visible focus; modal blocks page; close and reset work; Overview after refresh; no horizontal page overflow | Matched using mocked API | Passed | Playwright browser checks |
| UI-05 | AC3, AC7 | Angular | Record and validate income, expense, bill and budget; rename; navigate months | Existing operations and success feedback remain available | Matched | Passed | Existing `ledger-page.spec.ts` cases |
| UI-06 | AC7 | Angular | Load failure, invalid entries, conflict, failed expense/bill/budget/payment and rejected name | Show errors without false success; preserve relevant edit and retry load where applicable | Matched for tested scenarios | Passed | `ledger-page.spec.ts`: failure, invalid-input and retry cases |
| UI-07 | AC3 | Angular | Existing app status, amount and month regression tests | All pass | 56 tests across 4 files passed, including UI cases above | Passed | `npm test -- --watch=false` |
| UI-08 | AC1-AC8 | Build | Compile frontend | Build succeeds | Succeeded | Passed | `npm run build` |
| UI-09 | AC3, AC7 | End-to-end | Live API/database integration after UI change | Existing operations work with live services | Not run | Not run | Frontend-only change; mock API used |
| UI-10 | AC8 | Angular | Fire `beforeunload` for edited, unchanged, reverted and closed dialogs, and edits outside dialogs | Request warning only for edited open dialogs | Matched for both dialog types | Passed | `ledger-page.spec.ts`: leave-page warning cases |
| UI-11 | AC2, AC8 | Browser | Refresh an edited expense, navigate away with an edited bill, close an edited dialog, and refresh after non-dialog edits | Browser warning for edited dialogs; immediate discard on close; no warning for other edits | Warning appeared on refresh and navigation; other checks matched | Passed | Playwright browser checks with mocked API |
| UI-12 | AC8 | Browser | Cancel the browser refresh warning | Stay on page with the draft intact | Open dialog and draft retained | Passed | Independent Chrome DevTools check with mocked API |

Initial test and build commands were run from the workspace parent and failed
with missing `package.json`; rerunning from `frontend/` passed. The first modal
test run failed because the old tests expected expandable forms and jsdom lacks
dialog methods; updated tests passed. Browser checks exposed an Escape-key issue,
which was fixed and rechecked. An initial mock setup also timed out before its
test interception was corrected. The automated browser resolved a later
leave-page warning before cancellation could be verified. An independent Chrome
DevTools check subsequently verified cancellation successfully. After the
merge, the frontend suite again passed all 56 tests against the merged files.
