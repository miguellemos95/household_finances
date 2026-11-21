# Project Context

This directory is the authoritative, version-controlled project context.

## Status

Project rules registered at the user's request. Household requirements and initial architecture are documented. GitHub issues #1-#4 are registered; the user explicitly authorized creating them and beginning with #1. Issue #1 is completed and closed; local app/API checks and PostgreSQL container integration pass. Issue #2 is complete and closed after PR [#6](https://github.com/miguellemos95/household_finances/pull/6) merged on 2026-11-21 and its acceptance criteria were verified. Remaining product decisions are deferred to the relevant feature tickets.

## Confirmed Goal and Constraints

| ID | Type | Requirement |
| --- | --- | --- |
| GOAL-001 | Product goal | Manage shared household finances for the user and their girlfriend. |
| TECH-001 | Technology constraint | Use Angular for the frontend. |
| TECH-002 | Technology constraint | Use Python for the backend. |
| TECH-003 | Architecture decision | Use FastAPI for the REST API. |
| TECH-004 | Architecture decision | Use PostgreSQL with SQLAlchemy and Alembic for relational persistence and migrations. Use decimal-safe amounts for EUR. |
| NFR-001 | Maintainability | Follow SOLID, DRY, and KISS; keep code simple and avoid hacks and workarounds. |
| NFR-002 | Testability | Make implementations testable and include tests for every implementation. |
| NFR-003 | Consistency | Prevent drift between agreed requirements, architecture, code, tests, and context documentation. |
| NFR-004 | Error handling | Include application error-handling scenarios in the consolidated test table; infrastructure failover is not currently in scope. |

Feature-level requirements are tracked in [Personal Expense Tracking](personal-expense-tracking.md). The user has not requested elevated security or privacy requirements. Access model, deployment, accessibility expectations, and other applicable non-functional requirements remain to be clarified rather than assumed.

## Required Workflow

1. Clarify the request with the user. Record confirmed requirements and unresolved questions without guessing.
2. Register each feature/use case in a Markdown file under `context/` and link it in the feature index below.
3. Analyze requirements and design the solution/architecture before implementation. Discuss decisions with the user and record their rationale and status.
4. Draft a ticket with a title and description for the user to register, unless the user explicitly asks the assistant to register it in GitHub. Include scope, acceptance criteria, relevant context, and intended verification.
5. Before implementation, require an actual registered ticket ID. When the assistant creates an issue at the user's explicit request, record the returned issue ID against the feature/use case; a draft ticket is not implementation approval.
6. Implement only the agreed ticket scope, including tests and the consolidated test and failover table.
7. Execute relevant feature and regression tests and record actual results and any failures or limitations. Keep context, diagrams, decisions, and implementation aligned; raise scope changes with the user.
8. Once implementation, verification, and documentation are complete, open a pull request referencing the registered issue. If verification is blocked or fails, report it honestly rather than presenting the work as verified.
9. The user reviews and approves the pull request. Do not merge without explicit user authorization. Keep evidence and communication concise and grounded in actual results to avoid unnecessary token use.
10. After the user merges the pull request, verify the associated issue's acceptance criteria. Close the issue if completed; otherwise report what remains open.
11. When the issue is closed and all work and relevant documentation for the session are complete, tell the user to close the session. If anything remains unfinished or unpushed, identify it instead of saying the session is complete.

## Feature Index

| Feature / use case | Status | Ticket |
| --- | --- | --- |
| [Personal expense tracking](personal-expense-tracking.md) | Issues #1-#3 closed; #4 implementation and layout fix merged into `docs-run-project` in PRs #10 and #11; issue #4 remains open with gaps to address | [#1](https://github.com/miguellemos95/household_finances/issues/1), [#2](https://github.com/miguellemos95/household_finances/issues/2), [#3](https://github.com/miguellemos95/household_finances/issues/3), [#4](https://github.com/miguellemos95/household_finances/issues/4) |

Each future feature/use-case document must capture:

- Registered ticket ID and status; use "awaiting registration" before an ID is supplied.
- Objective, actors, scope, and exclusions confirmed with the user.
- Functional and applicable non-functional requirements, with traceable identifiers.
- Acceptance criteria, normal flow, and agreed failure/alternative flows.
- Requirement analysis, solution design, affected boundaries, and approved decisions.
- Relevant glossary terms, domain model, sequence diagrams, and other needed diagrams.
- Open questions and unresolved decisions.
- Tests, the consolidated test and failover table, and execution evidence.

## Ticket Draft Format

```text
Title: <concise change or outcome>

Description:
Objective: <confirmed need>
Context: <feature/use-case document>
Scope: <agreed inclusions and exclusions>
Requirements and acceptance criteria: <traceable, testable conditions>
Design: <agreed approach and relevant decisions>
Verification: <tests and failure/failover scenarios>
Open questions: <unresolved items, or none>

Registered ticket ID: awaiting user registration
```

## Test and Error-Handling Table

Every implementation must provide a consolidated table covering all its tests and application error-handling scenarios. The user clarified that this primarily means application error handling; infrastructure failover is out of current scope.

| Test ID | Requirement / acceptance criterion | Level | Scenario / failure condition | Expected outcome / recovery | Actual outcome | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |

Do not mark unexecuted tests as passed. Distinguish planned, not run, passed, failed, and blocked results. Record execution commands and relevant evidence with the feature documentation.

## Models and Decisions

The household glossary, domain model, data model, sequence diagrams, and selected FastAPI/PostgreSQL architecture are documented in [Personal Expense Tracking](personal-expense-tracking.md). They should be refined as remaining behavior is confirmed; keep diagrams in Markdown where practical.

## Clarification Backlog

- Income is one amount per partner per month. Should income entries later have dates, and can either partner have multiple income sources?
- Are financial records editable/deletable, and is a description/payee needed? Until decided, a mistaken entry cannot be corrected in the app.
- Should categories remain fixed or be user-configurable?
- What account/access model and deployment environment are needed? Must hosting itself have zero cost?
- What accessibility expectations apply?

These are pending questions, not assumed requirements. The FastAPI/PostgreSQL decision, the issue #2 decisions, and the registered issue mapping are in `personal-expense-tracking.md`. Resolve remaining product questions before implementing the affected later issues.