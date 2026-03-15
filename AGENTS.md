# AGENTS.md

## Purpose of this file
This file defines working rules for automated agents and AI tools operating on this repository.
Agents should treat this document as the default source of rules when analyzing, refactoring, and extending the project.

---

## Priorities
For every change, follow this order:

1. Preserve working code
2. Preserve architectural consistency
3. Keep the scope of changes minimal
4. Maintain readability and testability
5. Follow the repository’s existing conventions

Do not perform large rewrites if the problem can be solved with a small and safe refactor.

---

## Architecture rules

### Layer separation
The project maintains a clear separation of responsibilities between layers:

- `ui` — presentation and input handling layer
- `app` — orchestration, routing, application states
- `core` — business logic, domain model, simulation

If the repository uses different directory names, preserve their meaning and follow the existing structure.

### Allowed dependencies
- `app` may depend on `ui` and `core`
- `ui` must not implement business logic
- `core` must not depend on `ui`
- `core` must not depend on `pygame`

### Communication between layers
Communication between layers should happen through:
- events
- commands
- explicitly passed state

Avoid direct business logic calls from the UI layer.

### Pygame
- `pygame` imports must be limited to the UI layer
- where possible, `pygame` imports should be lazy so tests and CI can run without a graphical environment

---

## Code change rules

### Preferred style of changes
- first analyze the existing code
- adapt to the existing names, directory layout, and style
- extend existing solutions instead of creating parallel duplicates
- do not delete files without a clear reason

### Main entrypoint
- `main.py` should remain thin
- application startup logic should be delegated to the `app` layer

### Refactoring
If a refactor changes responsibility boundaries, dependencies, or communication between layers, evaluate whether an ADR is needed.

---

## Testing rules

### General
- every business logic change should include tests or preserve existing tests
- prefer stable tests that are resilient to small implementation changes
- avoid brittle tests that depend on rendering details or internal call ordering unless that behavior is the actual requirement
- Maintain test coverage above 95%.

### What to test
Prefer testing:
- contracts
- events and commands
- routing in the `app` layer
- logic in `core`

Limit testing of:
- implementation details
- private methods unless there is a clear reason
- direct `pygame` rendering if the behavior can be tested without GUI

### GUI
- logic tests must work without `pygame`
- tests should not require a graphical environment unless the repository explicitly has a separate set of GUI integration tests

### Architecture tests
Architecture rules should be enforced automatically through architecture tests, preferably using PyTestArch.

---

## Documentation rules

### README
Update the README only when a change affects:
- how the project is run
- how tests are run
- the architectural structure
- environment requirements

Do not rewrite the entire README unless necessary.
Adapt to the existing style and document structure.

### ADR

Add an ADR whenever a change:

- introduces a new architectural rule
- changes layer boundaries
- changes the communication model between modules
- changes how architecture quality is enforced
- introduces a significant technical decision with long-term consequences
- adds, replaces, upgrades in a meaningful way, or removes an external dependency, library, framework, or major tool used by the project

Do not add ADRs for small implementation details, minor refactors, routine internal code changes, or dependency updates that are purely mechanical and have no architectural or operational impact.

This repository already contains ADRs. The agent must preserve and follow the existing ADR structure used in the project.  
Before adding a new ADR, inspect the current ADR files and match their:

- directory location
- numbering scheme
- file naming convention
- section layout
- level of detail
- writing style

New ADRs must be added in the same format and convention already used in the repository.

When a change introduces or meaningfully changes an external dependency or library, the agent must evaluate whether an ADR is required. In general, an ADR is required when the dependency affects architecture, development workflow, testing strategy, CI/CD, deployment, runtime environment, maintainability, or long-term project direction.

For dependency-related ADRs, explain at least:

- why the dependency is being introduced or changed
- what problem it solves
- which alternatives were considered
- what trade-offs it introduces
- what impact it has on architecture, maintenance, testing, CI/CD, or runtime environment
---

## CI/CD rules
- do not create a new workflow if the existing one can be extended
- adapt changes to the existing workflow style
- if architecture tests are part of `pytest`, add them to the existing test step
- if the repository has separate quality gates, integrate with them
- before creating PR/MR, run locally every quality step defined in `.github/workflows/ci.yml`
- run these CI/CD steps at the very end of work (after all code/doc changes), as the final validation pass
- include in the final report a short command-by-command status for all executed CI/CD checks
- do not claim CI parity if any required local step was skipped

CI/CD changes should be minimal and consistent with the repository’s current setup.

---

## Rules for working on an existing repository
Before making changes, the agent should inspect:
- the `src/` structure
- the `tests/` structure
- existing workflows in `.github/workflows/`
- the presence and format of ADRs
- the README style
- the current application entrypoint
- the current way tests are run

Do not assume the repository is empty or that a new structure can be imposed.

---

## Expected agent workflow
For larger changes:
1. analyze the current state of the repository
2. propose a minimal scope of changes
3. implement the changes
4. run tests
5. run SCA/lint checks
6. update documentation if needed
7. determine whether an ADR is needed
8. run all local steps mirrored from `.github/workflows/ci.yml` as the final gate before finishing
9. ensure CI/CD still validates what it should

---

## Implementation preferences
- prefer simple, readable code
- prefer explicit dependencies over hidden singletons
- prefer small classes and functions with a single responsibility
- prefer composition over excessive inheritance
- prefer contracts and protocols where they help separate layers

---

## What to avoid
- mixing business logic with rendering
- importing `pygame` outside the UI layer
- large refactors without clear need
- duplicating existing mechanisms
- changing the README/ADR/workflow style just because another style seems nicer
- brittle tests tied to implementation details

---

## Change checklist
Before finishing work, check:
- whether the UI / App / Core separation is preserved
- whether communication goes through events/commands
- whether tests pass
- whether SCA/lint checks pass
- whether architecture tests cover new rules
- whether the README needs an update
- whether an ADR is needed
- whether CI/CD still validates everything it should
- whether all CI/CD pipeline steps from `.github/workflows/ci.yml` were executed locally by the agent before finishing work
