# TestPilot AI --- Full Project Development Plan

**Version:** 1.0\
**Project Type:** AI-assisted autonomous software testing, quality
assurance, security assessment, and issue management platform\
**Primary Goal:** Build a practical, deployable platform that can
explore authorized web applications, generate and execute tests,
identify functional and security issues, collect reproducible evidence,
create developer tickets, and verify fixes through automated retesting.

------------------------------------------------------------------------

## Document Guide

This plan is organized into parts so it can be used as a project
blueprint rather than a loose idea list.

-   **Part I --- Product Definition:** Vision, goals, users, scope,
    non-goals, and product principles.
-   **Part II --- Functional Requirements:** Detailed modules, user
    journeys, features, and expected behavior.
-   **Part III --- Technical Architecture:** System components,
    architecture, stack, AI orchestration, and execution design.
-   **Part IV --- Data & API Design:** Initial database model,
    relationships, API contract, and data lifecycle.
-   **Part V --- Testing and Security:** Test strategies, security
    scanning boundaries, safe execution controls, and evidence
    requirements.
-   **Part VI --- UI/UX Specification:** Pages, navigation, dashboard,
    scan experience, and issue workflow.
-   **Part VII --- Implementation Roadmap:** Phases, deliverables,
    acceptance criteria, and recommended development sequence.
-   **Part VIII --- Deployment & Operations:** Local development,
    containers, CI/CD, observability, and production considerations.
-   **Part IX --- Risks & Quality:** Technical risks, mitigations,
    validation, and project quality criteria.
-   **Part X --- Portfolio & Demonstration:** Demo scenarios,
    documentation, and resume presentation.

------------------------------------------------------------------------

# PART I --- PRODUCT DEFINITION

## 1. Product Overview

TestPilot AI is an AI-assisted software quality platform designed to
reduce repetitive manual testing of web applications. A user provides an
authorized application URL, configuration, and optional credentials or
API specifications. TestPilot explores the application, builds an
understanding of its pages and interactions, proposes test scenarios,
executes tests through browser and API tooling, evaluates actual
results, and produces evidence-backed findings.

The platform is not intended to let a language model freely control
every action or claim that a test passed based on generated text. AI is
used for planning, interpretation, prioritization, and explanations.
Deterministic tools perform actions, validations, and evidence capture.

The product should progressively support a complete quality workflow:

1.  Register an application and testing environment.
2.  Define the permitted scope and testing rules.
3.  Discover application pages, controls, forms, routes, and APIs.
4.  Build an application map.
5.  Generate a test plan and test cases.
6.  Review or approve tests when required.
7.  Execute tests in an isolated browser environment.
8.  Collect screenshots, traces, logs, requests, responses, and timings.
9.  Validate outcomes using assertions and observable evidence.
10. Group related failures and identify duplicate findings.
11. Create tickets with reproducible steps and evidence.
12. Assign findings to developers or teams.
13. Re-test fixes and perform targeted regression testing.
14. Track application quality and trends across scan runs.

### Product positioning

**TestPilot AI is an autonomous QA assistant that explores, tests,
investigates, documents, and follows up on software defects.**

The core value is not simply generating test scripts. It is reducing the
time required to discover application behavior, execute meaningful
tests, investigate failures, and create high-quality developer-ready
reports.

------------------------------------------------------------------------

## 2. Product Vision

The long-term vision is for TestPilot to maintain a useful, evolving
model of an application and its quality history.

A first scan discovers the application and creates its initial map.
Later scans compare the current application against previous
discoveries, detect changes, identify potentially affected tests, and
prioritize regression testing. Findings remain connected to the page,
component, API, test case, evidence, and ticket that produced them.

Over time, the platform should help answer questions such as:

-   Which parts of the application were tested?
-   Which pages or APIs have the highest failure rate?
-   What changed since the last scan?
-   Which tests should run after a code change?
-   Which defects are recurring?
-   Which failures are likely related?
-   Which findings are confirmed and which require human review?
-   Did a developer's fix actually resolve the issue?
-   What is the current quality risk of this release?

------------------------------------------------------------------------

## 3. Product Goals

### 3.1 Primary goals

-   Automate repetitive web application exploration and testing.
-   Generate useful test cases from discovered application behavior.
-   Execute tests reliably through browser automation and API tools.
-   Validate outcomes through observable evidence.
-   Detect functional errors, regressions, and selected security
    weaknesses.
-   Produce clear, reproducible bug reports.
-   Attach screenshots and relevant execution artifacts to issues.
-   Support assignment and developer workflow.
-   Re-test fixed defects and report verification results.
-   Provide a clear history of test runs and application quality.

### 3.2 Secondary goals

-   Reduce the amount of manual test authoring required.
-   Help teams discover overlooked edge cases.
-   Make test results understandable to developers and non-QA
    stakeholders.
-   Enable repeatable testing of staging and development environments.
-   Support integration with existing issue-management workflows.
-   Provide a portfolio-quality demonstration of AI, backend,
    automation, security, and system design.

### 3.3 Success criteria

The MVP should be considered successful when it can reliably:

-   Create and configure a testing project.
-   Explore a permitted target website.
-   Identify a meaningful set of pages and interactive elements.
-   Generate test cases for discovered features.
-   Execute browser tests without relying on unverified AI claims.
-   Record pass, fail, blocked, skipped, and inconclusive states.
-   Capture screenshots and execution logs for failures.
-   Create a structured bug report.
-   Assign an issue to a configured developer.
-   Export a scan report.
-   Re-run a failed test and compare its result.

Success should be measured using system reliability and quality, not the
number of AI features or UI screens.

------------------------------------------------------------------------

## 4. Intended Users and Personas

### 4.1 QA Engineer

Needs to quickly discover application flows, generate test cases,
execute tests, review failures, and maintain regression coverage.

### 4.2 Developer

Needs actionable bug reports, reproduction steps, relevant logs,
screenshots, request details, and a way to confirm that a fix resolved
the defect.

### 4.3 QA Lead or Engineering Lead

Needs a summary of application health, test coverage, defect severity,
recurring failures, quality trends, and release readiness.

### 4.4 Project Administrator

Needs to manage projects, environments, credentials, permissions, scan
policies, integrations, and retention settings.

### 4.5 Solo Developer or Small Team

Needs an affordable automated testing assistant that does not require a
large dedicated QA team or a complex enterprise setup.

------------------------------------------------------------------------

## 5. Product Principles

1.  **Evidence before claims:** A result must be based on observed
    behavior, logs, assertions, or other evidence.
2.  **AI plans, tools execute:** AI-generated plans are separated from
    deterministic execution and verification.
3.  **Safe by default:** Scans are scoped, rate-limited, and
    non-destructive unless a permitted test explicitly enables
    controlled behavior.
4.  **Human control:** Users can review, approve, stop, or exclude
    tests.
5.  **Explainability:** Every finding should explain why it was raised
    and what evidence supports it.
6.  **Reproducibility:** Tests and findings should contain enough
    information to repeat the observed behavior.
7.  **No false certainty:** The system distinguishes confirmed failures,
    suspected issues, and inconclusive results.
8.  **Incremental intelligence:** The platform builds application
    knowledge across scans without silently assuming that old
    observations are still valid.
9.  **Privacy:** Credentials, tokens, personal information, and
    sensitive response data should be protected and redacted from
    reports where appropriate.
10. **Practical extensibility:** Modules and integrations should be
    replaceable without redesigning the whole system.

------------------------------------------------------------------------

## 6. Scope and Non-Goals

### 6.1 MVP scope

-   Project and environment management.
-   Authorized URL scope configuration.
-   Browser-based application discovery.
-   Page, form, and interaction inventory.
-   Application map.
-   AI-assisted test generation.
-   Test review and approval.
-   Browser test execution using Playwright.
-   Deterministic assertions.
-   Screenshot and trace capture.
-   Browser console and failed-request collection.
-   Basic API checks.
-   Findings and issue management.
-   Manual developer assignment.
-   GitHub Issues integration.
-   Scan and test history.
-   Basic dashboard and report export.
-   Re-run failed tests.

### 6.2 Out of scope for the initial MVP

-   Unrestricted internet-wide scanning.
-   Aggressive penetration testing.
-   Exploit execution against third-party systems.
-   Automated destructive actions on production.
-   Real payments, emails, purchases, or irreversible transactions.
-   Full mobile-native application testing.
-   Complete replacement of enterprise Jira workflows.
-   Large-scale distributed test execution.
-   Fully autonomous code modification and pull-request creation.
-   Guaranteed root-cause diagnosis.
-   Guaranteed detection of every defect or vulnerability.

These may be considered later only after the foundational execution,
evidence, permission, and reliability systems are mature.

------------------------------------------------------------------------

# PART II --- FUNCTIONAL REQUIREMENTS

## 7. Module 1: Project and Environment Management

A TestPilot project represents an application that will be tested. A
project can contain multiple environments, such as local development,
staging, QA, or a controlled test deployment.

### 7.1 Project creation

Required fields:

-   Project name.
-   Description.
-   Application base URL.
-   Project owner.
-   Default environment.
-   Time zone.
-   Optional repository URL.
-   Optional application documentation or OpenAPI file.

### 7.2 Environment configuration

Each environment should store:

-   Environment name.
-   Base URL.
-   Environment type.
-   Authentication profile.
-   Allowed domain list.
-   Excluded paths.
-   Scan policy.
-   Request rate limits.
-   Environment-specific variables.
-   Environment status.

Example environments:

-   Local
-   Development
-   QA
-   Staging

Production should require stricter controls and should be disabled for
destructive or high-impact tests by default.

### 7.3 Project settings

Settings should include:

-   Default browser.
-   Default viewport.
-   Scan timeout.
-   Maximum exploration depth.
-   Maximum pages.
-   Maximum test execution duration.
-   Maximum concurrent browser sessions.
-   Retry policy.
-   Artifact retention.
-   AI model selection.
-   Security scan profile.
-   Ticket integration settings.

### 7.4 Acceptance criteria

-   A user can create, edit, archive, and delete projects according to
    permissions.
-   A project can contain multiple environments.
-   A scan cannot begin until a valid target and scan policy exist.
-   The application validates URLs and target scope before execution.
-   Project settings are versioned or snapshotted into each scan run so
    results remain interpretable later.

------------------------------------------------------------------------

## 8. Module 2: Application Discovery and Explorer

### 8.1 Purpose

The Explorer automatically navigates the authorized application to
discover pages, routes, links, forms, controls, and visible workflows.

It should not assume that a sitemap or static route list contains every
part of the application. Discovery should combine several sources:

-   Links visible on pages.
-   Browser navigation.
-   Forms and interactive controls.
-   URL changes.
-   Application route patterns.
-   Network requests.
-   Optional sitemap.
-   Optional OpenAPI documentation.

### 8.2 Discovery workflow

1.  Validate the configured target.
2.  Check that the initial URL is within the permitted scope.
3.  Launch an isolated browser context.
4.  Apply the configured authentication profile if enabled.
5.  Open the initial page.
6.  Record page title, URL, viewport, load state, and relevant DOM
    information.
7.  Identify links, buttons, inputs, selects, tabs, menus, forms, and
    other interactive controls.
8.  Build candidate navigation actions.
9.  Prioritize actions according to discovery policy.
10. Navigate to candidate pages and record results.
11. Detect repeated pages or route loops.
12. Stop when the exploration limits are reached.
13. Persist discovered entities and the discovery summary.

### 8.3 Discovered entity types

**Page**

-   URL.
-   Route pattern.
-   Title.
-   Page type.
-   Discovery method.
-   Authentication requirement, if observed.
-   Parent page.
-   Screenshot.
-   Last-seen scan.

**Element**

-   Element type.
-   Accessible name or label.
-   Selector candidates.
-   Page association.
-   Visibility.
-   Interactivity.
-   Observed attributes.
-   Confidence.
-   Last-seen scan.

**Form**

-   Form name or label.
-   Associated page.
-   Input fields.
-   Required indicators.
-   Submit action.
-   Validation behavior.
-   Submission outcome.

**Navigation edge**

-   Source page.
-   Destination page.
-   Trigger element.
-   Action type.
-   Whether the navigation was successful.

### 8.4 Exploration safeguards

-   Stay within the configured domain and path scope.
-   Do not follow links to external sites unless explicitly allowed.
-   Do not automatically submit forms that may cause real-world side
    effects.
-   Avoid destructive buttons such as delete, purchase, transfer, send,
    or publish unless a safe test policy explicitly permits them.
-   Detect logout and session-expiration behavior.
-   Prevent loops and excessive repeated interactions.
-   Limit pages, actions, depth, duration, and request rate.
-   Provide a stop control.
-   Record blocked actions and why they were blocked.

### 8.5 Application map

The Explorer should generate a graph representation of the application.

Nodes:

-   Pages.
-   Forms.
-   API endpoints.
-   Optional modules.

Edges:

-   Navigation.
-   Form submission.
-   API relationship.
-   Redirect.
-   Authentication transition.

The map should support:

-   Zoom.
-   Pan.
-   Search.
-   Filter by page type.
-   Highlight newly discovered nodes.
-   Highlight failed nodes.
-   Highlight pages without tests.
-   Open page details.
-   View associated tests and findings.

### 8.6 Acceptance criteria

-   Discovery produces a structured page and element inventory.
-   Repeated routes are deduplicated.
-   Exploration limits are enforced.
-   External navigation is blocked unless allowed.
-   Discovery actions are logged.
-   The user can review the discovered map.
-   Failed or blocked exploration is reported honestly.

------------------------------------------------------------------------

## 9. Module 3: AI Test Planner and Test Case Generation

### 9.1 Purpose

The AI Test Planner converts discovered application structure and
user-defined testing goals into structured test cases.

The AI must produce a schema-conforming test plan rather than
unstructured prose.

### 9.2 Inputs

-   Application map.
-   Page and element inventory.
-   Form metadata.
-   Authentication state.
-   API specification, if supplied.
-   Existing test cases.
-   Scan policy.
-   User testing goals.
-   Previous failures and regressions, when relevant.

### 9.3 Test categories

**Functional tests**

-   Page loading.
-   Navigation.
-   Form submission.
-   CRUD behavior where safe.
-   Search.
-   Filters.
-   Sorting.
-   Pagination.
-   Modal behavior.
-   Authentication.
-   Logout.

**Validation tests**

-   Required fields.
-   Invalid data.
-   Boundary values.
-   Format validation.
-   Length limits.
-   Duplicate values.
-   Empty inputs.

**Edge-case tests**

-   Long inputs.
-   Unicode.
-   Unexpected whitespace.
-   Invalid dates.
-   Missing optional values.
-   Repeated clicks.
-   Slow responses.
-   Empty result sets.

**Regression tests**

-   Previously failing tests.
-   Tests associated with changed pages.
-   Tests related to modified components or endpoints.
-   Tests with historical instability.

**Accessibility tests**

-   Accessible names.
-   Keyboard interaction.
-   Focus order.
-   Contrast checks where tooling permits.
-   Semantic structure.
-   Form labels.

### 9.4 Test case schema

Every generated test case should include:

-   Unique ID.
-   Title.
-   Description.
-   Category.
-   Priority.
-   Risk.
-   Preconditions.
-   Target page or endpoint.
-   Steps.
-   Action definitions.
-   Expected outcomes.
-   Assertions.
-   Data requirements.
-   Side-effect classification.
-   Estimated execution duration.
-   Confidence.
-   Source observations.
-   Review status.

### 9.5 Example test case

**ID:** LOGIN-FUNC-001\
**Title:** User can log in with valid credentials\
**Category:** Functional\
**Priority:** P1

**Preconditions:**

-   Login page discovered.
-   Test account exists.
-   Account credentials are available in the configured secret store.

**Steps:**

1.  Open login page.
2.  Enter configured email.
3.  Enter configured password.
4.  Submit login form.
5.  Wait for the expected authenticated state.

**Assertions:**

-   Authentication succeeds.
-   The expected dashboard or authenticated page appears.
-   The URL is consistent with the expected login flow.
-   No unexpected error is observed.

**Evidence:**

-   Before screenshot.
-   After screenshot.
-   Navigation event.
-   Relevant network requests.
-   Assertion results.

### 9.6 Test generation strategy

Use a staged approach:

1.  Generate candidate scenarios.
2.  Validate test schema.
3.  Remove duplicates.
4.  Check for unsafe actions.
5.  Check whether required data and preconditions exist.
6.  Identify ambiguous tests.
7.  Assign confidence and risk.
8.  Send tests for review when required.
9.  Store approved test definitions.

Do not execute a test merely because an LLM generated it. The policy and
validation layers must approve it.

### 9.7 Test plan review

Users should be able to:

-   View generated tests.
-   Edit titles and descriptions.
-   Change priorities.
-   Modify steps.
-   Disable tests.
-   Approve tests.
-   Approve a whole test suite.
-   Reject tests.
-   Regenerate selected tests.
-   See why a test was generated.

### 9.8 Acceptance criteria

-   Test cases are generated from discovered information.
-   Output is validated against a structured schema.
-   Duplicate tests are detected.
-   Unsafe tests are blocked or require explicit review.
-   Each test has observable assertions.
-   The user can review and edit generated tests.
-   Approved tests are stored and versioned.

------------------------------------------------------------------------

## 10. Module 4: Test Execution Engine

### 10.1 Purpose

The Execution Engine runs approved tests in isolated browser contexts
and evaluates actual outcomes.

The LLM should not be the execution engine. Playwright and controlled
test tools should execute actions.

### 10.2 Execution responsibilities

-   Allocate a worker.
-   Create a browser session.
-   Configure browser and viewport.
-   Load authentication state.
-   Execute steps.
-   Validate assertions.
-   Capture artifacts.
-   Record timings.
-   Collect logs.
-   Handle errors and timeouts.
-   Clean up the browser.
-   Persist the execution result.

### 10.3 Supported actions

Initial action types:

-   Navigate.
-   Click.
-   Fill.
-   Select.
-   Check.
-   Uncheck.
-   Press key.
-   Hover.
-   Scroll.
-   Wait for condition.
-   Capture screenshot.
-   Assert text.
-   Assert visible.
-   Assert hidden.
-   Assert URL.
-   Assert value.
-   Assert element count.
-   Assert API response.
-   Assert response schema.

Actions should be represented as typed, validated objects. Do not permit
arbitrary code execution in generated test steps.

### 10.4 Execution states

A test run may have:

-   Queued.
-   Initializing.
-   Running.
-   Passed.
-   Failed.
-   Blocked.
-   Skipped.
-   Timed out.
-   Cancelled.
-   Inconclusive.

A failed assertion is not the same as a browser infrastructure error.
The result model must preserve that distinction.

### 10.5 Execution isolation

Each test should run with:

-   Separate browser context.
-   Configured timeout.
-   Restricted network policy.
-   Controlled cookies and storage.
-   Test-specific credentials.
-   Limited access to filesystem artifacts.
-   Cleanup after execution.

### 10.6 Retry policy

Retries should be used carefully.

-   Retry infrastructure failures according to policy.
-   Do not retry every functional assertion automatically.
-   Preserve the first failure.
-   Record retry attempts.
-   Identify flaky behavior.
-   Avoid masking intermittent defects by marking a test passed solely
    because a later retry succeeded.

### 10.7 Acceptance criteria

-   Tests execute using the defined action schema.
-   Assertions are evaluated deterministically.
-   Results are stored with timestamps.
-   Browser errors are classified.
-   Timeouts and cancellation work.
-   Artifacts are collected on failure and optionally on pass.
-   A test run can be rerun.
-   Execution logs can be inspected.

------------------------------------------------------------------------

## 11. Module 5: API Testing

### 11.1 Endpoint discovery

API endpoints can be discovered from:

-   OpenAPI specifications.
-   Swagger documentation.
-   Browser network activity.
-   User-supplied endpoint lists.
-   Explicitly configured route patterns.

The platform should record the source of each endpoint.

### 11.2 Endpoint inventory

Store:

-   Method.
-   URL template.
-   Path parameters.
-   Query parameters.
-   Request body schema.
-   Response schemas.
-   Authentication requirements.
-   Observed status codes.
-   Source.
-   Environment.
-   Last-seen scan.

### 11.3 API test categories

-   Status-code validation.
-   Response schema validation.
-   Required-field validation.
-   Data type validation.
-   Missing parameter behavior.
-   Invalid parameter behavior.
-   Authentication requirements.
-   Authorization checks within configured test identities.
-   Error response consistency.
-   Rate-limit behavior, using controlled low-volume tests.
-   CORS policy review.
-   Response data exposure review.

### 11.4 API execution

The API engine should:

1.  Validate the endpoint against scope.
2.  Check the action against the scan policy.
3.  Resolve authentication safely.
4.  Construct the request.
5.  Execute within timeout and rate limits.
6.  Store sanitized request and response metadata.
7.  Evaluate assertions.
8.  Collect evidence.
9.  Create findings when supported by evidence.

### 11.5 Acceptance criteria

-   Endpoints are stored and deduplicated.
-   API tests can run independently of browser tests.
-   Requests remain within scope.
-   Sensitive data is redacted.
-   Assertions are reproducible.
-   Endpoint findings link back to the scan and test case.

------------------------------------------------------------------------

## 12. Module 6: Security Intelligence Engine

### 12.1 Purpose

The Security Engine performs controlled, authorized security checks and
reports evidence-backed risks.

It must be separate from general functional testing so that security
policies, scan intensity, and permissions can be managed independently.

### 12.2 Initial security categories

**HTTP and transport configuration**

-   HTTPS enforcement.
-   TLS certificate validity.
-   Redirect behavior.
-   Mixed content.
-   Selected security headers.
-   Cookie security attributes.

**Application configuration**

-   Exposed debug information.
-   Verbose errors.
-   Sensitive data in client responses.
-   Insecure configuration indicators.
-   Directory listing where relevant.

**Authentication and session**

-   Authentication-required endpoints.
-   Session invalidation after logout.
-   Cookie flags.
-   Session handling observations.
-   Login error information disclosure.
-   Configurable lockout or throttling behavior.

**API security**

-   Authentication checks.
-   Authorization checks using authorized test accounts.
-   Object access control observations.
-   Excessive response data.
-   Input validation.
-   HTTP method handling.
-   CORS.
-   Rate-limit behavior.

**Input-handling checks**

-   Controlled non-destructive input validation.
-   Safe reflection checks.
-   Basic injection indicators.
-   Output encoding observations.

### 12.3 Security scan profiles

**Passive Profile**

-   Header review.
-   TLS and certificate checks.
-   Cookie attributes.
-   Response metadata.
-   Passive information exposure.
-   No state-changing requests.

**Standard Profile**

-   Passive checks.
-   Controlled input validation.
-   Authentication and authorization checks using test accounts.
-   Limited low-volume requests.
-   No destructive operations.

**Advanced Profile**

-   Additional checks enabled only after explicit scope and permission
    review.
-   Strict rate and time limits.
-   Separate execution environment.
-   Detailed audit log.
-   Explicit exclusions and stop conditions.

The MVP should focus on Passive and Standard profiles.

### 12.4 Finding confidence

Each security finding must be classified as one of:

-   Confirmed: reproduced and supported by strong evidence.
-   Probable: strong indicators exist, but confirmation is incomplete.
-   Potential: a pattern warrants investigation.
-   Informational: configuration or observation with no demonstrated
    exploitability.

Do not label an issue as a confirmed vulnerability solely because an AI
model suspects it.

### 12.5 Severity

Severity should combine:

-   Impact.
-   Likelihood.
-   Exploitability evidence.
-   Scope.
-   Data sensitivity.
-   Confidence.

The platform should allow a human to override the severity with a
recorded reason.

### 12.6 Security safeguards

-   Explicit authorization.
-   Target allowlist.
-   Domain and path scope.
-   Request rate limits.
-   Maximum scan duration.
-   Maximum request count.
-   Stop conditions.
-   Safe test payloads.
-   No destructive testing by default.
-   No real transactions.
-   No unauthorized privilege escalation.
-   No uncontrolled external requests.
-   Audit logs.
-   Secret redaction.
-   Scan cancellation.

### 12.7 Acceptance criteria

-   Security checks are policy-controlled.
-   Findings include evidence and confidence.
-   Scan scope is enforced.
-   Rate limits and stop conditions work.
-   Sensitive data is redacted.
-   Users can review the scan policy.
-   Security findings are distinct from functional failures.

------------------------------------------------------------------------

## 13. Module 7: Evidence Collector

### 13.1 Purpose

The Evidence Collector records enough information to understand,
reproduce, and verify a test result.

### 13.2 Artifact types

-   Screenshot.
-   Browser trace.
-   Video, if enabled.
-   Console log.
-   Page error.
-   Request metadata.
-   Response metadata.
-   Assertion output.
-   DOM snapshot or selected DOM context.
-   Test steps.
-   Timestamp.
-   Browser version.
-   Viewport.
-   Environment identifier.
-   Test case identifier.

### 13.3 Screenshot behavior

Screenshots should be collected:

-   Before risky or important actions when useful.
-   After navigation.
-   At failure.
-   At the end of a test.
-   When a security finding requires visual context.

The platform should support:

-   Full-page screenshot.
-   Viewport screenshot.
-   Screenshot annotation.
-   Highlighted target element.
-   Thumbnail generation.

### 13.4 Sensitive data handling

Before artifacts are stored or shared:

-   Mask password fields.
-   Redact tokens and secrets.
-   Avoid recording unnecessary personal data.
-   Apply configured redaction rules.
-   Limit access to sensitive artifacts.
-   Use expiring signed URLs where storage supports them.
-   Record artifact access where appropriate.

### 13.5 Acceptance criteria

-   Evidence is associated with the exact execution.
-   Artifacts are stored independently from database records.
-   Artifact references remain stable.
-   Redaction rules are applied.
-   Evidence can be viewed from test results and findings.
-   Retention and deletion policies are enforced.

------------------------------------------------------------------------

## 14. Module 8: Bug Intelligence and Finding Management

### 14.1 Purpose

Convert raw test failures into actionable findings.

The AI may assist with:

-   Summarizing failures.
-   Suggesting a cause.
-   Grouping similar failures.
-   Detecting duplicates.
-   Recommending severity.
-   Identifying affected pages or endpoints.
-   Suggesting remediation.

The deterministic system supplies the underlying facts.

### 14.2 Finding structure

Each finding should contain:

-   Finding ID.
-   Project.
-   Scan.
-   Test case.
-   Execution.
-   Page or endpoint.
-   Category.
-   Title.
-   Description.
-   Expected result.
-   Actual result.
-   Reproduction steps.
-   Severity.
-   Confidence.
-   Status.
-   First detected.
-   Last detected.
-   Evidence links.
-   AI analysis.
-   Developer assignment.
-   External ticket reference.

### 14.3 Duplicate detection

Possible duplicate signals:

-   Same page or endpoint.
-   Similar error message.
-   Same assertion failure.
-   Same response code.
-   Similar stack trace.
-   Similar screenshot or visual region.
-   Same underlying component.

Duplicate detection should initially suggest duplicates rather than
automatically merging them. Users should be able to confirm or reject
the grouping.

### 14.4 Finding lifecycle

Suggested states:

-   New.
-   Triaged.
-   Assigned.
-   In Progress.
-   Fixed.
-   Ready for Retest.
-   Verified.
-   Reopened.
-   Won't Fix.
-   Duplicate.
-   False Positive.

### 14.5 AI analysis

AI-generated analysis should include:

-   What failed.
-   What evidence supports it.
-   Likely cause, clearly labelled as a hypothesis.
-   Possible affected component.
-   Suggested investigation.
-   Suggested fix direction.
-   Confidence.

It must not claim a root cause has been proven unless the evidence
actually proves it.

------------------------------------------------------------------------

## 15. Module 9: Ticket Management and Developer Assignment

### 15.1 Internal ticketing

The MVP should include a simple internal issue system. This ensures the
platform works without requiring external integrations.

### 15.2 Ticket fields

-   Title.
-   Description.
-   Project.
-   Environment.
-   Severity.
-   Category.
-   Status.
-   Assignee.
-   Reporter.
-   Created date.
-   Updated date.
-   Linked finding.
-   Linked test.
-   Linked execution.
-   Attachments.
-   External ticket ID.

### 15.3 Assignment

Initial assignment options:

-   Manual assignment.
-   Assign to team.
-   Assign using configured module ownership.
-   Assign using a repository ownership map.

Avoid opaque AI assignment in the MVP. AI can recommend a person or
team, but the system should use explicit rules and allow confirmation.

### 15.4 GitHub Issues integration

MVP integration:

-   Connect repository using OAuth or a carefully scoped token.
-   Select repository.
-   Create issue.
-   Map TestPilot severity and labels.
-   Attach evidence links.
-   Include reproduction steps.
-   Include expected and actual behavior.
-   Store GitHub issue number and URL.
-   Synchronize status in a limited, documented manner.

A ticket should not include secrets, raw credentials, or unnecessary
personal data.

### 15.5 Future integrations

-   Jira.
-   Linear.
-   GitLab Issues.
-   Slack or Microsoft Teams notifications.

### 15.6 Acceptance criteria

-   Findings can be converted into tickets.
-   Tickets can be assigned internally.
-   GitHub issues can be created.
-   Evidence links are accessible to authorized users.
-   External ticket identifiers are stored.
-   Duplicate issue creation can be prevented or warned about.

------------------------------------------------------------------------

## 16. Module 10: Automated Retesting and Regression

### 16.1 Purpose

When a finding is marked Ready for Retest, TestPilot should re-execute
the associated test and determine whether the original failure persists.

### 16.2 Retest workflow

1.  User or integration marks the finding ready for retest.
2.  TestPilot retrieves the original test definition and environment.
3.  The test runs in a fresh browser context.
4.  The original assertion is evaluated.
5.  Related regression tests may run.
6.  Evidence is collected.
7.  The result is attached to the finding.
8.  The finding is marked Verified if the verification policy passes.
9.  If the original failure persists, the finding returns to an active
    state.
10. If the result is inconclusive, human review is required.

### 16.3 Regression selection

MVP:

-   Re-run the original failing test.
-   Re-run tests in the same page or module.
-   Re-run tests explicitly selected by the user.

Future:

-   Compare application maps.
-   Detect route or element changes.
-   Identify related tests.
-   Use dependency information.
-   Prioritize regression tests based on risk and historical failures.

### 16.4 Acceptance criteria

-   Retests use the original test and environment configuration.
-   Original and new evidence are retained.
-   Fix verification is based on assertions.
-   Inconclusive results are not treated as successful fixes.
-   Retest history is visible.

------------------------------------------------------------------------

## 17. Module 11: Reports and Quality Analytics

### 17.1 Dashboard metrics

-   Projects.
-   Environments.
-   Total scans.
-   Tests executed.
-   Passed.
-   Failed.
-   Blocked.
-   Inconclusive.
-   Pass rate.
-   Open findings.
-   Critical and high findings.
-   Average test duration.
-   Recent scan trend.
-   Flaky tests.
-   Regression failures.

### 17.2 Scan report

A scan report should contain:

-   Project and environment.
-   Scan configuration.
-   Scan date and duration.
-   Discovery summary.
-   Pages discovered.
-   Elements discovered.
-   APIs discovered.
-   Tests generated.
-   Tests executed.
-   Test results.
-   Security checks.
-   Findings.
-   Evidence.
-   Limitations.
-   Overall summary.

### 17.3 Report formats

MVP:

-   In-app report.
-   HTML export.

Later:

-   PDF export.
-   CSV export for test cases and findings.
-   API report.
-   Scheduled reports.

### 17.4 Quality score

A quality score may be introduced later, but it should not be presented
as a scientifically precise measure of application quality.

If implemented, show the formula and its inputs. A score should not hide
critical failures or substitute for detailed results.

------------------------------------------------------------------------

# PART III --- TECHNICAL ARCHITECTURE

## 18. Architecture Overview

Use a modular architecture with a web application, API, scan
orchestration, execution workers, AI services, data stores, and
integrations.

### 18.1 Logical components

**Frontend**

-   Project dashboard.
-   Scan configuration.
-   Application Explorer.
-   Test planner.
-   Live execution.
-   Findings.
-   Ticket management.
-   Analytics.

**Backend API**

-   Authentication.
-   Authorization.
-   Project management.
-   Environment management.
-   Scan management.
-   Test management.
-   Findings.
-   Tickets.
-   Integrations.
-   Reports.

**Orchestrator**

-   Creates scan workflows.
-   Tracks progress.
-   Schedules jobs.
-   Enforces scan policies.
-   Coordinates discovery, planning, execution, security, and reporting.

**Browser workers**

-   Launch isolated browser sessions.
-   Execute Playwright steps.
-   Collect screenshots and traces.
-   Report results.

**API test workers**

-   Execute controlled API checks.
-   Validate schemas.
-   Capture sanitized request/response evidence.

**AI service**

-   Application interpretation.
-   Test generation.
-   Failure analysis.
-   Duplicate suggestions.
-   Remediation explanations.

**Data layer**

-   PostgreSQL for structured application data.
-   Redis for job coordination and transient state.
-   Object storage for artifacts.

**Integration service**

-   GitHub.
-   Future issue providers.
-   Notifications.

### 18.2 Suggested MVP deployment model

Start with a modular monolith for the control plane and separate worker
processes for browser execution.

This keeps development manageable while allowing later service
extraction.

Suggested services:

-   `web`: React frontend.
-   `api`: FastAPI backend.
-   `worker`: Celery worker for orchestration and general jobs.
-   `browser-worker`: Playwright execution worker.
-   `postgres`: relational database.
-   `redis`: queue, coordination, cache.
-   `object-storage`: MinIO for local development.
-   `ollama`: optional local model service.

Do not split everything into microservices initially. Use well-defined
modules and interfaces so components can be separated if scaling needs
arise.

------------------------------------------------------------------------

## 19. Recommended Technology Stack

### Frontend

-   React.
-   Vite.
-   JavaScript rather than TypeScript, if maintaining the user's
    preferred stack.
-   Tailwind CSS.
-   React Router.
-   TanStack Query.
-   Recharts.
-   React Flow or a similar graph visualization library for the
    application map.
-   A reusable component system.

### Backend

-   Python.
-   FastAPI.
-   Pydantic for schemas and validation.
-   SQLAlchemy.
-   Alembic migrations.
-   Celery for background jobs.

### Automation

-   Playwright.
-   Browser contexts.
-   Browser traces.
-   Screenshots.
-   Browser console and request event listeners.

### AI

-   Provider abstraction.
-   Local Ollama option.
-   Hosted model option.
-   Structured output.
-   Prompt and model version tracking.
-   Retry and validation layer.

### Data

-   PostgreSQL.
-   Redis.
-   MinIO or S3-compatible object storage.

### Monitoring

-   Structured application logs.
-   Prometheus metrics, when needed.
-   Grafana dashboards, later in the roadmap.
-   Error tracking.

### Development and deployment

-   Docker.
-   Docker Compose.
-   GitHub Actions.
-   Environment-based configuration.
-   Secret management.

------------------------------------------------------------------------

## 20. AI Orchestration Design

Do not create a single unrestricted agent with every tool available.

Use a controlled pipeline of specialized tasks.

### 20.1 Discovery Interpreter

Inputs:

-   Page metadata.
-   DOM summaries.
-   Link and element inventory.
-   Navigation observations.

Outputs:

-   Page classification.
-   Element classification.
-   Candidate workflows.
-   Discovery confidence.
-   Structured page summaries.

### 20.2 Test Planner

Inputs:

-   Discovery output.
-   Test policy.
-   Existing test suite.
-   User goals.

Outputs:

-   Test cases.
-   Preconditions.
-   Steps.
-   Assertions.
-   Priorities.
-   Risk.
-   Review recommendations.

### 20.3 Test Validator

This is primarily deterministic.

Checks:

-   Schema validity.
-   Allowed action types.
-   Target scope.
-   Unsafe action classification.
-   Missing preconditions.
-   Timeout values.
-   Required assertions.
-   Duplicate test candidates.

### 20.4 Execution Agent

The AI may select from validated actions, but execution should be
through an allowlisted action library.

It should not be allowed to generate arbitrary Python, shell,
JavaScript, or browser scripts for execution.

### 20.5 Failure Analyst

Inputs:

-   Failed assertion.
-   Browser error.
-   Console logs.
-   Network events.
-   Screenshot.
-   Test steps.
-   Page metadata.

Outputs:

-   Failure summary.
-   Likely cause.
-   Evidence references.
-   Suggested investigation.
-   Confidence.

### 20.6 Issue Analyst

Inputs:

-   Findings.
-   Existing tickets.
-   Finding history.

Outputs:

-   Duplicate candidates.
-   Category.
-   Severity recommendation.
-   Suggested assignment.
-   Ticket title and description.

### 20.7 Model provider interface

Define a common interface for AI providers so model choice can change
without rewriting product modules.

The interface should support:

-   Structured generation.
-   Prompt version.
-   Model identifier.
-   Token usage where available.
-   Latency.
-   Error handling.
-   Validation.
-   Redaction policy.

------------------------------------------------------------------------

## 21. Browser Automation Architecture

### 21.1 Browser session lifecycle

1.  Worker receives a validated job.
2.  Worker loads the execution configuration.
3.  Worker creates an isolated browser context.
4.  Worker loads approved authentication state.
5.  Worker performs the test.
6.  Worker captures required evidence.
7.  Worker emits structured execution events.
8.  Worker closes browser context.
9.  Worker uploads artifacts.
10. Worker reports completion.

### 21.2 Browser action abstraction

Use an action interface instead of direct AI-generated code.

Example conceptual action:

-   Type: `click`
-   Target: approved selector or element reference.
-   Timeout: configured limit.
-   Preconditions: element visible and enabled.
-   Result: action outcome and evidence.

Action types should be validated before execution.

### 21.3 Selector strategy

Prefer selectors in this order:

1.  Accessible role and name.
2.  Label.
3.  Placeholder, when reliable.
4.  Test ID.
5.  Stable attributes.
6.  CSS selector.
7.  XPath as a last resort.

When multiple selectors are possible, store candidates and their
confidence. Avoid brittle selectors tied to generated CSS class names.

### 21.4 Browser event collection

Collect:

-   Console errors.
-   Page exceptions.
-   Failed requests.
-   Response status codes.
-   Navigation.
-   Redirects.
-   Request duration.
-   WebSocket events where supported and required.

Avoid recording full request or response bodies by default because they
may contain sensitive data.

------------------------------------------------------------------------

# PART IV --- DATA AND API DESIGN

## 22. Database Design

PostgreSQL should be the primary relational database. Artifact files
should be stored in object storage, with metadata and references stored
in PostgreSQL.

The following is an initial logical schema. It is not necessary to
implement every table during the first sprint.

### 22.1 Core tables

#### users

-   `id`
-   `email`
-   `display_name`
-   `password_hash` or external identity reference
-   `created_at`
-   `updated_at`

#### organizations

-   `id`
-   `name`
-   `created_at`

#### organization_members

-   `id`
-   `organization_id`
-   `user_id`
-   `role`
-   `created_at`

#### projects

-   `id`
-   `organization_id`
-   `name`
-   `slug`
-   `description`
-   `repository_url`
-   `owner_id`
-   `status`
-   `created_at`
-   `updated_at`

#### environments

-   `id`
-   `project_id`
-   `name`
-   `base_url`
-   `environment_type`
-   `auth_profile_id`
-   `scan_policy_id`
-   `status`
-   `created_at`
-   `updated_at`

#### auth_profiles

-   `id`
-   `project_id`
-   `name`
-   `auth_type`
-   `secret_reference`
-   `configuration_json`
-   `created_at`
-   `updated_at`

Credentials should be stored encrypted or in a secret manager, not as
plaintext in ordinary database fields.

#### scan_policies

-   `id`
-   `project_id`
-   `name`
-   `allowed_domains`
-   `allowed_paths`
-   `excluded_paths`
-   `allowed_test_categories`
-   `max_pages`
-   `max_depth`
-   `max_duration_seconds`
-   `max_requests`
-   `request_rate_limit`
-   `destructive_actions_allowed`
-   `security_profile`
-   `created_at`
-   `updated_at`

------------------------------------------------------------------------

## 23. Discovery Tables

#### scan_runs

-   `id`
-   `project_id`
-   `environment_id`
-   `scan_policy_snapshot`
-   `status`
-   `started_at`
-   `completed_at`
-   `initiated_by`
-   `summary_json`
-   `error_message`

#### discovered_pages

-   `id`
-   `scan_run_id`
-   `project_id`
-   `environment_id`
-   `url`
-   `route_pattern`
-   `title`
-   `page_type`
-   `parent_page_id`
-   `auth_state`
-   `discovery_source`
-   `last_seen_at`

#### discovered_elements

-   `id`
-   `discovered_page_id`
-   `element_type`
-   `accessible_name`
-   `label`
-   `selector_candidates_json`
-   `attributes_json`
-   `is_visible`
-   `is_interactive`
-   `confidence`
-   `last_seen_at`

#### discovered_forms

-   `id`
-   `discovered_page_id`
-   `name`
-   `fields_json`
-   `submit_element_id`
-   `validation_observations_json`
-   `last_seen_at`

#### discovered_endpoints

-   `id`
-   `project_id`
-   `scan_run_id`
-   `method`
-   `url_template`
-   `path`
-   `parameters_json`
-   `request_schema_json`
-   `response_schema_json`
-   `auth_observation`
-   `source`
-   `last_seen_at`

#### application_edges

-   `id`
-   `scan_run_id`
-   `source_page_id`
-   `destination_page_id`
-   `trigger_element_id`
-   `edge_type`
-   `observation_json`

------------------------------------------------------------------------

## 24. Test Tables

#### test_suites

-   `id`
-   `project_id`
-   `name`
-   `description`
-   `suite_type`
-   `created_at`
-   `updated_at`

#### test_cases

-   `id`
-   `project_id`
-   `test_suite_id`
-   `title`
-   `description`
-   `category`
-   `priority`
-   `risk_level`
-   `preconditions_json`
-   `steps_json`
-   `assertions_json`
-   `data_requirements_json`
-   `safety_classification`
-   `source_discovery_json`
-   `version`
-   `status`
-   `created_by`
-   `created_at`
-   `updated_at`

#### test_case_versions

-   `id`
-   `test_case_id`
-   `version`
-   `definition_json`
-   `created_by`
-   `created_at`

#### test_runs

-   `id`
-   `scan_run_id`
-   `project_id`
-   `environment_id`
-   `status`
-   `browser`
-   `started_at`
-   `completed_at`
-   `summary_json`

#### test_executions

-   `id`
-   `test_run_id`
-   `test_case_id`
-   `status`
-   `attempt_number`
-   `started_at`
-   `completed_at`
-   `duration_ms`
-   `failure_type`
-   `failure_message`
-   `assertion_results_json`
-   `execution_metadata_json`

#### execution_steps

-   `id`
-   `test_execution_id`
-   `step_number`
-   `action_type`
-   `action_definition_json`
-   `status`
-   `started_at`
-   `completed_at`
-   `result_json`
-   `error_message`

------------------------------------------------------------------------

## 25. Evidence Tables

#### artifacts

-   `id`
-   `project_id`
-   `scan_run_id`
-   `test_execution_id`
-   `finding_id`
-   `artifact_type`
-   `storage_key`
-   `mime_type`
-   `size_bytes`
-   `checksum`
-   `redaction_status`
-   `created_at`
-   `expires_at`

#### logs

-   `id`
-   `scan_run_id`
-   `test_execution_id`
-   `severity`
-   `source`
-   `message`
-   `metadata_json`
-   `created_at`

Store large screenshots, traces, videos, and exports in object storage.
Store references and metadata in the database.

------------------------------------------------------------------------

## 26. Finding and Ticket Tables

#### findings

-   `id`
-   `project_id`
-   `scan_run_id`
-   `test_execution_id`
-   `test_case_id`
-   `discovered_page_id`
-   `discovered_endpoint_id`
-   `title`
-   `description`
-   `category`
-   `severity`
-   `confidence`
-   `status`
-   `expected_result`
-   `actual_result`
-   `reproduction_steps_json`
-   `ai_analysis_json`
-   `first_detected_at`
-   `last_detected_at`
-   `created_at`
-   `updated_at`

#### finding_artifacts

-   `id`
-   `finding_id`
-   `artifact_id`
-   `relationship_type`

#### finding_relations

-   `id`
-   `source_finding_id`
-   `target_finding_id`
-   `relation_type`
-   `confidence`
-   `created_at`

#### tickets

-   `id`
-   `project_id`
-   `finding_id`
-   `title`
-   `description`
-   `severity`
-   `status`
-   `assignee_user_id`
-   `team_id`
-   `created_by`
-   `external_provider`
-   `external_issue_id`
-   `external_issue_url`
-   `created_at`
-   `updated_at`

#### ticket_events

-   `id`
-   `ticket_id`
-   `actor_id`
-   `event_type`
-   `event_data_json`
-   `created_at`

#### retest_runs

-   `id`
-   `finding_id`
-   `test_case_id`
-   `test_execution_id`
-   `status`
-   `started_at`
-   `completed_at`
-   `result_summary_json`

### 26.1 Data relationships

-   Organization owns projects.
-   Project contains environments, scan policies, test suites, tests,
    findings, and tickets.
-   Environment belongs to a project.
-   Scan run belongs to a project and environment.
-   Discovery entities are associated with scan runs.
-   Test runs belong to scan runs.
-   Test executions belong to test runs and test cases.
-   Artifacts belong to executions, scans, or findings.
-   Findings may link to tests, executions, pages, and endpoints.
-   Tickets may link to findings and external issues.
-   Retests link findings to new test executions.

### 26.2 Database design rules

-   Use UUID identifiers.
-   Use foreign keys.
-   Add indexes for project, scan, status, severity, and timestamp
    queries.
-   Use JSONB for flexible metadata, not as a replacement for all
    relational columns.
-   Keep secrets out of ordinary records.
-   Use migrations.
-   Preserve historical scan and test definitions.
-   Avoid deleting records needed for audit and reproducibility without
    an explicit retention process.

------------------------------------------------------------------------

## 27. API Design

Use REST APIs for the MVP and WebSockets for live scan and test
progress.

### 27.1 Authentication

-   `POST /api/v1/auth/login`
-   `POST /api/v1/auth/logout`
-   `GET /api/v1/auth/me`

Use a secure authentication strategy with appropriate session or token
handling. Apply authorization to every project, environment, scan,
finding, ticket, and artifact request.

### 27.2 Projects

-   `GET /api/v1/projects`
-   `POST /api/v1/projects`
-   `GET /api/v1/projects/{project_id}`
-   `PATCH /api/v1/projects/{project_id}`
-   `DELETE /api/v1/projects/{project_id}`

### 27.3 Environments

-   `GET /api/v1/projects/{project_id}/environments`
-   `POST /api/v1/projects/{project_id}/environments`
-   `PATCH /api/v1/environments/{environment_id}`
-   `DELETE /api/v1/environments/{environment_id}`

### 27.4 Discovery

-   `POST /api/v1/projects/{project_id}/discovery`
-   `GET /api/v1/discovery/{scan_run_id}`
-   `GET /api/v1/discovery/{scan_run_id}/pages`
-   `GET /api/v1/discovery/{scan_run_id}/elements`
-   `GET /api/v1/discovery/{scan_run_id}/map`
-   `POST /api/v1/discovery/{scan_run_id}/stop`

### 27.5 Test cases

-   `GET /api/v1/projects/{project_id}/test-suites`
-   `POST /api/v1/projects/{project_id}/test-suites`
-   `GET /api/v1/test-suites/{suite_id}/tests`
-   `POST /api/v1/test-suites/{suite_id}/tests/generate`
-   `POST /api/v1/test-cases`
-   `GET /api/v1/test-cases/{test_case_id}`
-   `PATCH /api/v1/test-cases/{test_case_id}`
-   `POST /api/v1/test-cases/{test_case_id}/approve`
-   `POST /api/v1/test-cases/{test_case_id}/disable`

### 27.6 Execution

-   `POST /api/v1/test-runs`
-   `GET /api/v1/test-runs/{test_run_id}`
-   `GET /api/v1/test-runs/{test_run_id}/executions`
-   `GET /api/v1/test-executions/{execution_id}`
-   `POST /api/v1/test-executions/{execution_id}/rerun`
-   `POST /api/v1/test-runs/{test_run_id}/cancel`

### 27.7 Findings

-   `GET /api/v1/projects/{project_id}/findings`
-   `GET /api/v1/findings/{finding_id}`
-   `PATCH /api/v1/findings/{finding_id}`
-   `POST /api/v1/findings/{finding_id}/retest`
-   `POST /api/v1/findings/{finding_id}/ticket`

### 27.8 Tickets

-   `GET /api/v1/projects/{project_id}/tickets`
-   `POST /api/v1/tickets`
-   `GET /api/v1/tickets/{ticket_id}`
-   `PATCH /api/v1/tickets/{ticket_id}`
-   `POST /api/v1/tickets/{ticket_id}/assign`
-   `POST /api/v1/tickets/{ticket_id}/sync`

### 27.9 Reports and artifacts

-   `GET /api/v1/scan-runs/{scan_run_id}/report`
-   `GET /api/v1/artifacts/{artifact_id}`
-   `POST /api/v1/reports/export`

### 27.10 WebSocket events

Example event types:

-   `scan.started`
-   `discovery.page_found`
-   `discovery.element_found`
-   `discovery.completed`
-   `test_plan.generated`
-   `test_run.started`
-   `test_execution.started`
-   `test_execution.step_completed`
-   `test_execution.failed`
-   `artifact.created`
-   `finding.created`
-   `ticket.created`
-   `retest.completed`
-   `scan.completed`
-   `scan.failed`

Events should include IDs, timestamps, event type, and a safe payload.
Avoid sending secrets or raw sensitive data through event messages.

------------------------------------------------------------------------

# PART V --- TESTING AND SECURITY

## 28. TestPilot's Own Testing Strategy

TestPilot must be tested as a product. The platform's ability to test
other applications does not replace testing its own components.

### 28.1 Backend tests

-   Unit tests.
-   Schema validation.
-   Authorization tests.
-   Project isolation.
-   API tests.
-   Database tests.
-   Queue tests.
-   Integration tests.
-   Error handling.

### 28.2 Frontend tests

-   Component tests.
-   Form validation.
-   Navigation.
-   Scan status display.
-   Test result rendering.
-   Finding management.
-   Ticket assignment.
-   Loading and error states.

### 28.3 Worker tests

-   Browser lifecycle.
-   Action validation.
-   Selector handling.
-   Timeout behavior.
-   Cancellation.
-   Artifact collection.
-   Retry behavior.
-   Worker failure recovery.

### 28.4 AI tests

-   Structured output validity.
-   Prompt regression tests.
-   Hallucination-resistant output validation.
-   Duplicate test generation.
-   Unsafe test rejection.
-   AI provider failure handling.
-   Model version comparison.

### 28.5 End-to-end tests

Use a controlled demo application with known defects.

TestPilot should be run against that application to validate:

-   Discovery.
-   Test generation.
-   Execution.
-   Failure detection.
-   Evidence.
-   Ticket creation.
-   Retesting.

------------------------------------------------------------------------

## 29. Safe Execution and Security Controls

### 29.1 Authorization

The user must confirm they have permission to test the target. For
public-facing or third-party applications, explicit authorization must
be obtained.

### 29.2 Target scope

Every scan should enforce:

-   Allowed hosts.
-   Allowed ports where applicable.
-   Allowed paths.
-   Excluded paths.
-   Redirect scope.
-   External-link policy.

### 29.3 SSRF prevention

Because users can provide URLs, the platform must prevent requests to:

-   Loopback addresses.
-   Private infrastructure not explicitly authorized.
-   Cloud metadata endpoints.
-   Internal control-plane services.
-   Disallowed IP ranges.
-   Hostnames that resolve into blocked addresses.

DNS resolution and redirect checks should be performed throughout
execution, not only at initial validation. Browser and worker egress
should be isolated with network controls.

### 29.4 Destructive action prevention

Actions such as:

-   Delete.
-   Purchase.
-   Send.
-   Transfer.
-   Publish.
-   Invite.
-   Change password.
-   Modify production data.

Should be blocked or require explicit safe test configuration and
controlled test data.

### 29.5 Credential handling

-   Do not store credentials in plaintext.
-   Use encrypted storage or secret references.
-   Mask secrets in logs.
-   Avoid including credentials in AI prompts.
-   Restrict access to authentication profiles.
-   Use dedicated test accounts.
-   Prefer short-lived credentials when possible.

### 29.6 Isolation

-   Browser workers should run in isolated containers or similarly
    constrained environments.
-   Avoid sharing browser contexts across projects.
-   Limit filesystem access.
-   Limit network access.
-   Apply CPU, memory, duration, and process limits.
-   Clean up execution environments.

### 29.7 Audit trail

Record:

-   Who started the scan.
-   Target.
-   Environment.
-   Scope.
-   Policy.
-   Start and stop times.
-   Actions executed.
-   Blocked actions.
-   Findings.
-   Ticket operations.
-   Configuration changes.

------------------------------------------------------------------------

# PART VI --- UI/UX SPECIFICATION

## 30. Global Navigation

Recommended sidebar:

-   Overview.
-   Projects.
-   Applications.
-   Scans.
-   Test Suites.
-   Findings.
-   Tickets.
-   Security.
-   Reports.
-   Integrations.
-   Settings.

The initial MVP can simplify this to:

-   Dashboard.
-   Projects.
-   Scans.
-   Tests.
-   Findings.
-   Tickets.
-   Settings.

------------------------------------------------------------------------

## 31. Dashboard

### Purpose

Provide a high-level view of application testing activity and quality.

### Components

-   Project selector.
-   Scan summary.
-   Tests passed versus failed.
-   Open findings.
-   Severity distribution.
-   Recent scans.
-   Recent findings.
-   Latest regression results.
-   Scan activity graph.

### UX requirements

-   Metrics must be clickable and lead to filtered detail pages.
-   Empty states should explain how to create the first project or scan.
-   Loading and error states must be designed.
-   Metrics should not imply quality certainty beyond their underlying
    data.

------------------------------------------------------------------------

## 32. Project Overview

Show:

-   Project name.
-   Environment.
-   Base URL, appropriately masked if necessary.
-   Latest scan status.
-   Discovered page count.
-   Test suite count.
-   Pass rate.
-   Open findings.
-   Security summary.
-   Recent activity.

Tabs:

-   Overview.
-   Explorer.
-   Test Suites.
-   Scans.
-   Findings.
-   Tickets.
-   Settings.

------------------------------------------------------------------------

## 33. Scan Configuration

The user should configure:

-   Target environment.
-   Scope.
-   Discovery depth.
-   Page limit.
-   Test categories.
-   Security profile.
-   Authentication profile.
-   Request limits.
-   Time limit.
-   Exclusions.
-   Approval requirements.

Before starting, show a scan summary:

-   Target.
-   Included scope.
-   Excluded scope.
-   Planned scan types.
-   Estimated limits.
-   Safety policy.

The user should confirm before the scan begins.

------------------------------------------------------------------------

## 34. Live Scan View

Display progress in real time.

Sections:

-   Current stage.
-   Pages discovered.
-   Current page.
-   Current action.
-   Tests generated.
-   Tests completed.
-   Findings.
-   Errors.
-   Timeline.

Provide:

-   Stop scan.
-   Pause, if supported.
-   View logs.
-   View browser session, where safe.
-   View current artifacts.

Do not fabricate percentage progress when the system cannot estimate it.
Use stage-based progress and actual counters.

------------------------------------------------------------------------

## 35. Application Explorer

Display:

-   Page graph.
-   Page list.
-   Route.
-   Page title.
-   Element count.
-   Forms.
-   Associated tests.
-   Associated findings.

Page detail panel:

-   Screenshot.
-   URL.
-   Discovery metadata.
-   Elements.
-   Forms.
-   API calls.
-   Test coverage.
-   Findings.

------------------------------------------------------------------------

## 36. Test Case Editor

Display:

-   Test title.
-   Category.
-   Priority.
-   Preconditions.
-   Steps.
-   Assertions.
-   Target page.
-   Test data.
-   Safety classification.
-   Generated source observations.
-   Review state.

Actions:

-   Edit.
-   Approve.
-   Reject.
-   Regenerate.
-   Duplicate.
-   Disable.
-   Execute.

The editor should make generated tests understandable to users who are
not automation specialists.

------------------------------------------------------------------------

## 37. Test Execution Detail

Display:

-   Overall status.
-   Duration.
-   Browser.
-   Environment.
-   Step timeline.
-   Assertions.
-   Screenshots.
-   Console errors.
-   Network failures.
-   Trace.
-   Retry history.

A failed step should be visually distinct, and the user should be able
to open the exact evidence associated with it.

------------------------------------------------------------------------

## 38. Findings Page

Filters:

-   Status.
-   Severity.
-   Category.
-   Environment.
-   Module.
-   Assignee.
-   Scan.
-   Date.

Finding detail:

-   Title.
-   Description.
-   Severity.
-   Confidence.
-   Expected and actual result.
-   Reproduction steps.
-   Evidence.
-   Related tests.
-   AI analysis.
-   Ticket.
-   History.
-   Retest action.

------------------------------------------------------------------------

## 39. Ticket Detail

Display:

-   Ticket title.
-   Status.
-   Assignee.
-   Severity.
-   Finding.
-   Evidence.
-   Reproduction steps.
-   External issue link.
-   Activity history.
-   Retest status.

Actions:

-   Assign.
-   Change status.
-   Add comment.
-   Create GitHub issue.
-   Synchronize external status.
-   Start retest.

------------------------------------------------------------------------

# PART VII --- IMPLEMENTATION ROADMAP

## 40. Phase 0: Product and Engineering Setup

**Estimated duration: 3--5 days**

### Objectives

-   Finalize MVP scope.
-   Create repository.
-   Define architecture.
-   Set up development environment.
-   Establish code quality standards.

### Tasks

-   Create Git repository.
-   Establish branches.
-   Define project structure.
-   Create frontend and backend projects.
-   Configure Docker Compose.
-   Set up PostgreSQL.
-   Set up Redis.
-   Configure environment variables.
-   Create initial database migration.
-   Configure linting and formatting.
-   Configure test runners.
-   Create CI workflow.

### Deliverables

-   Repository.
-   Architecture notes.
-   Development environment.
-   Running frontend and backend.
-   Database connectivity.
-   CI pipeline.

### Acceptance criteria

-   A developer can clone the project and run the stack.
-   Health endpoints work.
-   Database migrations execute.
-   CI checks run.

------------------------------------------------------------------------

## 41. Phase 1: Authentication, Organizations, and Projects

**Estimated duration: 1 week**

### Objectives

Build the platform's identity and project foundation.

### Tasks

-   Authentication.
-   User profile.
-   Organization model.
-   Organization membership.
-   Role-based access.
-   Project CRUD.
-   Environment CRUD.
-   Project settings.
-   Scan policy model.
-   Secret storage abstraction.

### Deliverables

-   Login and logout.
-   Dashboard shell.
-   Project list.
-   Project creation.
-   Project detail.
-   Environment management.
-   Authorization middleware.

### Acceptance criteria

-   Users can create projects.
-   Users can configure environments.
-   Users cannot access projects they are not authorized to access.
-   Sensitive credentials are not stored as plaintext.
-   Project data is isolated.

------------------------------------------------------------------------

## 42. Phase 2: Browser Worker Foundation

**Estimated duration: 1--2 weeks**

### Objectives

Create a reliable, isolated browser automation worker.

### Tasks

-   Install and configure Playwright.
-   Create browser worker container.
-   Create browser session manager.
-   Implement context lifecycle.
-   Implement safe navigation.
-   Implement allowed-domain validation.
-   Implement timeouts.
-   Implement cancellation.
-   Implement browser event collection.
-   Implement screenshot capture.
-   Implement trace capture.
-   Implement artifact upload.
-   Implement worker status reporting.

### Deliverables

-   Browser worker.
-   Safe navigation.
-   Browser action abstraction.
-   Artifact storage.
-   Execution logs.

### Acceptance criteria

-   Worker can launch and close browser sessions.
-   Worker can navigate to an authorized page.
-   Out-of-scope navigation is blocked.
-   Timeout works.
-   Cancellation works.
-   Screenshots and traces are stored.
-   Worker failure is reported to the backend.

------------------------------------------------------------------------

## 43. Phase 3: Application Discovery

**Estimated duration: 1--2 weeks**

### Objectives

Discover the application structure and build an application map.

### Tasks

-   Initial page capture.
-   Page metadata extraction.
-   Link discovery.
-   Interactive element extraction.
-   Form detection.
-   Route tracking.
-   Navigation edge creation.
-   Discovery deduplication.
-   Exploration depth.
-   Page limits.
-   Scope enforcement.
-   Discovery event streaming.
-   Explorer UI.
-   Application map.

### Deliverables

-   Discovery worker.
-   Page inventory.
-   Element inventory.
-   Form inventory.
-   Application map.
-   Discovery report.

### Acceptance criteria

-   Discovery works on a controlled multi-page test application.
-   Pages are deduplicated.
-   Loops are controlled.
-   Limits are enforced.
-   External navigation is blocked.
-   Results persist and can be viewed after the scan.

------------------------------------------------------------------------

## 44. Phase 4: AI Test Planning

**Estimated duration: 1--2 weeks**

### Objectives

Generate structured test cases based on discovered application behavior.

### Tasks

-   AI provider interface.
-   Prompt versioning.
-   Discovery summarization.
-   Test case schema.
-   Functional test generation.
-   Validation test generation.
-   Edge-case test generation.
-   Duplicate detection.
-   Test validation.
-   Test plan UI.
-   Editing and approval.

### Deliverables

-   AI test planner.
-   Test generation API.
-   Test case persistence.
-   Test review UI.

### Acceptance criteria

-   AI generates structured test cases.
-   Invalid outputs are rejected or repaired.
-   Tests are traceable to discovered observations.
-   Duplicate candidates are identified.
-   Unsafe tests are blocked.
-   Users can review and approve tests.

------------------------------------------------------------------------

## 45. Phase 5: Test Execution

**Estimated duration: 2 weeks**

### Objectives

Execute generated test cases and produce deterministic results.

### Tasks

-   Test runner.
-   Step interpreter.
-   Action allowlist.
-   Selector resolver.
-   Assertion engine.
-   Execution state machine.
-   Timeout handling.
-   Retry handling.
-   Browser event collection.
-   Screenshot capture.
-   Execution detail UI.
-   Live progress.

### Deliverables

-   Test execution engine.
-   Test run history.
-   Execution detail page.
-   Live event updates.

### Acceptance criteria

-   Approved tests can be executed.
-   Steps and assertions are recorded.
-   Test results are deterministic where possible.
-   Failures have evidence.
-   Timeouts and cancellations work.
-   Test executions can be rerun.

------------------------------------------------------------------------

## 46. Phase 6: Evidence and Bug Intelligence

**Estimated duration: 1--2 weeks**

### Objectives

Convert execution failures into understandable findings.

### Tasks

-   Artifact model.
-   Object storage.
-   Artifact access.
-   Redaction.
-   Failure classification.
-   AI failure summary.
-   Finding schema.
-   Finding creation.
-   Duplicate suggestions.
-   Finding detail UI.
-   Report generation.

### Deliverables

-   Evidence collector.
-   Finding engine.
-   Bug report.
-   Screenshot viewer.
-   Execution-to-finding links.

### Acceptance criteria

-   Failed tests can produce findings.
-   Findings contain reproducible steps.
-   Evidence is linked.
-   Sensitive values are redacted.
-   AI analysis is clearly marked as analysis, not proven root cause.
-   Duplicate suggestions can be reviewed.

------------------------------------------------------------------------

## 47. Phase 7: API Testing

**Estimated duration: 1--2 weeks**

### Objectives

Add controlled API discovery and testing.

### Tasks

-   OpenAPI import.
-   Endpoint inventory.
-   Request schema parsing.
-   API test generation.
-   HTTP execution engine.
-   Response validation.
-   Authentication configuration.
-   Rate limits.
-   API evidence.
-   API findings.

### Deliverables

-   API inventory.
-   API test suite.
-   API execution engine.
-   API test result UI.

### Acceptance criteria

-   OpenAPI endpoints can be imported.
-   Endpoint scope is validated.
-   Requests execute with configured authentication.
-   Responses are validated.
-   Sensitive information is redacted.
-   Findings link to endpoints.

------------------------------------------------------------------------

## 48. Phase 8: Security Intelligence

**Estimated duration: 2 weeks for initial security capabilities**

### Objectives

Add safe, controlled web and API security checks.

### Tasks

-   Security policy.
-   Passive scan profile.
-   Standard profile.
-   Header checks.
-   Cookie checks.
-   TLS checks.
-   Error exposure checks.
-   CORS checks.
-   Controlled input validation.
-   Authentication checks.
-   Authorization checks using test accounts.
-   Severity classification.
-   Confidence classification.
-   Security finding UI.
-   Scan audit trail.

### Deliverables

-   Security engine.
-   Security profiles.
-   Findings.
-   Security dashboard.

### Acceptance criteria

-   Scan policy controls which checks can run.
-   Security checks remain within scope.
-   Request limits are enforced.
-   Findings include evidence.
-   Findings include confidence.
-   No destructive tests are performed by default.

------------------------------------------------------------------------

## 49. Phase 9: Ticketing and GitHub Integration

**Estimated duration: 1 week**

### Objectives

Connect findings to developer workflows.

### Tasks

-   Internal ticket system.
-   Ticket creation.
-   Assignee management.
-   Status lifecycle.
-   Team ownership configuration.
-   GitHub authentication.
-   Repository selection.
-   Issue creation.
-   Label mapping.
-   Evidence links.
-   External issue synchronization.
-   Duplicate ticket warning.

### Deliverables

-   Internal ticketing.
-   GitHub Issues integration.
-   Assignment workflow.

### Acceptance criteria

-   Finding can become a ticket.
-   Ticket can be assigned.
-   GitHub issue can be created.
-   Evidence and reproduction steps are included.
-   External issue is linked.
-   Duplicate issues are detected or warned about.

------------------------------------------------------------------------

## 50. Phase 10: Retesting and Regression

**Estimated duration: 1 week**

### Objectives

Verify fixes and build an initial regression workflow.

### Tasks

-   Retest action.
-   Original test retrieval.
-   Fresh execution.
-   Result comparison.
-   Retest artifact collection.
-   Finding status update.
-   Related regression selection.
-   Retest history.

### Deliverables

-   Retest workflow.
-   Regression test selection.
-   Fix verification UI.

### Acceptance criteria

-   Findings can be retested.
-   The original test is reused.
-   Evidence is preserved.
-   Fix status is based on assertions.
-   Inconclusive outcomes require review.

------------------------------------------------------------------------

## 51. Phase 11: Analytics, Reports, and Polish

**Estimated duration: 1 week**

### Objectives

Make the product understandable, presentable, and useful across multiple
scans.

### Tasks

-   Dashboard metrics.
-   Scan trends.
-   Finding trends.
-   Test coverage indicators.
-   Flaky test indicators.
-   HTML report.
-   Export.
-   Empty states.
-   Loading states.
-   Error states.
-   Accessibility improvements.
-   Responsive layout.
-   UX consistency.

### Deliverables

-   Final dashboard.
-   Reports.
-   Analytics.
-   Polished UX.

### Acceptance criteria

-   Dashboard metrics reconcile with underlying data.
-   Reports contain scan configuration and limitations.
-   User can inspect details behind metrics.
-   UX works across common desktop sizes.
-   Errors are presented clearly.

------------------------------------------------------------------------

# PART VIII --- DEPLOYMENT AND OPERATIONS

## 52. Local Development Environment

Use Docker Compose for repeatable local development.

Suggested services:

-   Frontend.
-   API.
-   General worker.
-   Browser worker.
-   PostgreSQL.
-   Redis.
-   MinIO.
-   Optional Ollama.

### Development requirements

-   `.env.example`.
-   Database migrations.
-   Seed script.
-   Demo project.
-   Demo target application.
-   Test data.
-   Local storage configuration.

The setup should be documented so a reviewer can run the application
without manually installing each dependency.

------------------------------------------------------------------------

## 53. CI/CD

GitHub Actions should run:

### Backend

-   Dependency installation.
-   Linting.
-   Unit tests.
-   Schema validation.
-   Integration tests where practical.

### Frontend

-   Dependency installation.
-   Linting.
-   Component tests.
-   Build.

### Container

-   Build images.
-   Scan dependencies and images.
-   Validate Docker Compose configuration.

### Release

-   Version tagging.
-   Build artifacts.
-   Deploy to staging.
-   Run smoke tests.
-   Promote to production only after checks pass.

------------------------------------------------------------------------

## 54. Observability

Monitor:

-   API latency.
-   API error rate.
-   Worker queue length.
-   Job execution duration.
-   Browser startup failures.
-   Test execution duration.
-   Scan cancellation.
-   AI provider latency.
-   AI provider failures.
-   Artifact upload errors.
-   Database performance.
-   Redis health.
-   Worker memory and CPU.

Logs should be structured and include correlation IDs:

-   Project ID.
-   Scan ID.
-   Test run ID.
-   Execution ID.
-   Worker ID.

Never log secrets or raw sensitive response data.

------------------------------------------------------------------------

## 55. Deployment Strategy

### Portfolio MVP

-   Docker Compose on a cloud VM.
-   Reverse proxy.
-   HTTPS.
-   PostgreSQL.
-   Redis.
-   Object storage.
-   API.
-   Frontend.
-   Worker processes.

### Production-like considerations

-   Persistent storage.
-   Backups.
-   Database migrations.
-   Secret management.
-   Worker isolation.
-   Network restrictions.
-   Artifact retention.
-   Rate limits.
-   Monitoring.
-   Alerting.
-   Resource quotas.

Browser workers are resource-intensive. They should not be deployed as
ordinary unrestricted web processes. Separate worker capacity and
resource limits are important.

------------------------------------------------------------------------

# PART IX --- RISKS AND MITIGATION

## 56. Risk: AI generates incorrect tests

**Mitigation**

-   Structured output.
-   Schema validation.
-   Test review.
-   Deterministic assertions.
-   Confidence labels.
-   Execution evidence.
-   Prompt regression tests.

## 57. Risk: AI reports false bugs

**Mitigation**

-   Require observable evidence.
-   Distinguish failures from infrastructure errors.
-   Verify failures where practical.
-   Group duplicate failures.
-   Human triage.
-   Confidence classification.

## 58. Risk: Browser exploration causes side effects

**Mitigation**

-   Safe action policy.
-   Form submission classification.
-   Scope controls.
-   Destructive action blocking.
-   Explicit approval.
-   Test accounts.
-   Cancellation.

## 59. Risk: Security scans harm targets

**Mitigation**

-   Authorization confirmation.
-   Scope validation.
-   Rate limits.
-   Request limits.
-   Safe profiles.
-   Network restrictions.
-   Stop conditions.
-   Audit trail.

## 60. Risk: Browser workers become an attack surface

**Mitigation**

-   Isolated containers.
-   Restricted egress.
-   No host filesystem access.
-   Resource limits.
-   Ephemeral sessions.
-   Worker image hardening.
-   Secrets minimization.

## 61. Risk: Project becomes too large

**Mitigation**

-   MVP scope.
-   Sequential implementation.
-   Feature flags.
-   Modular architecture.
-   Acceptance criteria.
-   Avoid premature microservices.
-   Build a working end-to-end slice early.

## 62. Risk: AI cost and latency

**Mitigation**

-   Cache application summaries.
-   Use smaller models for classification.
-   Use larger models only for complex reasoning.
-   Limit prompt context.
-   Batch summarization.
-   Track model usage.
-   Allow local inference.
-   Add timeouts and fallback behavior.

## 63. Risk: Test instability

**Mitigation**

-   Accessible selectors.
-   Stable test IDs where possible.
-   Wait for conditions rather than fixed sleeps.
-   Fresh browser contexts.
-   Record traces.
-   Retry only infrastructure failures.
-   Track flaky tests.

------------------------------------------------------------------------

# PART X --- PORTFOLIO AND DEMONSTRATION

## 64. Demo application

Build or use a deliberately vulnerable but controlled demo application.
It should include known defects so TestPilot can demonstrate detection
and evidence.

Suggested modules:

-   Login.
-   Dashboard.
-   User management.
-   CRUD form.
-   Search.
-   Pagination.
-   API endpoints.
-   Role-based access.
-   A few intentionally introduced bugs.
-   A few safe security misconfigurations.

The target application must be separate from TestPilot. This
demonstrates that TestPilot can test an application rather than merely
test itself.

### Example known defects

-   Incorrect required-field validation.
-   Broken pagination.
-   Search ignores case incorrectly.
-   Invalid date accepted.
-   API returns incorrect status.
-   Missing authorization check in a controlled demo endpoint.
-   Excessive error details.
-   Missing security header.

Use only controlled, intentionally vulnerable defects and test data.

------------------------------------------------------------------------

## 65. Demo storyline

A strong portfolio demonstration should follow a story.

### Step 1 --- Create project

Add a demo application and its staging environment.

### Step 2 --- Configure scope

Define the allowed host and scan limits.

### Step 3 --- Start discovery

TestPilot explores the application and creates the page map.

### Step 4 --- Review discovered application

Show pages, forms, controls, endpoints, and navigation.

### Step 5 --- Generate tests

TestPilot creates functional and validation scenarios.

### Step 6 --- Execute tests

Show browser execution, test progress, and evidence capture.

### Step 7 --- Identify defects

Show a failed assertion with screenshot, console error, and reproduction
steps.

### Step 8 --- Create ticket

Create a developer ticket and assign it to a configured team member.

### Step 9 --- Fix defect

Make the fix in the demo application.

### Step 10 --- Retest

TestPilot reruns the original test and verifies the fix.

This end-to-end narrative will be more impressive than a collection of
isolated screenshots.

------------------------------------------------------------------------

## 66. GitHub Repository Requirements

The repository should include:

-   Clear README.
-   Product overview.
-   Architecture diagram.
-   Screenshots.
-   Demo video or GIF.
-   Feature list.
-   Technology stack.
-   Local setup.
-   Docker Compose instructions.
-   Environment variables.
-   Database migrations.
-   Demo credentials that are safe and only for the demo environment.
-   Sample test target.
-   Sample scan report.
-   API documentation.
-   Known limitations.
-   Roadmap.
-   License.

Never include real credentials, tokens, customer data, or private test
evidence.

------------------------------------------------------------------------

## 67. Resume Positioning

Once the platform is implemented and measured, a possible project
description could be:

**TestPilot AI --- Autonomous QA & Security Testing Platform**

-   Developed an AI-assisted QA platform that explores web applications,
    generates structured test scenarios, and executes browser-based
    functional and regression tests using Playwright.
-   Built an asynchronous test orchestration backend using FastAPI,
    Redis, and background workers, with evidence collection for failures
    including screenshots, execution traces, console errors, and failed
    network requests.
-   Implemented controlled API and security checks, evidence-backed
    defect reporting, issue tracking, developer assignment, and
    automated fix verification.

Only include the features that you have actually implemented. Replace
generic claims with measured results, such as number of pages explored,
tests executed, detection rate on a known demo dataset, average
execution duration, and model evaluation metrics.

------------------------------------------------------------------------

# PART XI --- PRIORITIZATION

## 68. Feature Priority

### P0 --- Must exist for MVP

-   Project and environment creation.
-   Authorization and scope controls.
-   Browser worker.
-   Application discovery.
-   Page and element inventory.
-   Test generation.
-   Test review.
-   Deterministic execution.
-   Assertions.
-   Screenshots.
-   Logs.
-   Findings.
-   Test history.
-   Basic report.
-   Rerun.

### P1 --- Strong next additions

-   API testing.
-   Security passive checks.
-   Internal ticketing.
-   Developer assignment.
-   GitHub integration.
-   Retest.
-   Regression tests.
-   Duplicate finding suggestions.

### P2 --- Advanced features

-   Jira and Linear.
-   Change-aware test selection.
-   Visual regression.
-   Accessibility testing.
-   AI-assisted test maintenance.
-   Test flakiness analysis.
-   Scheduled scans.
-   Multi-browser testing.
-   Parallel execution.
-   Team analytics.
-   Advanced security testing.
-   Pull request-triggered testing.

------------------------------------------------------------------------

## 69. Recommended Development Order

The most important engineering advice is to build an end-to-end vertical
slice as early as possible.

Do not wait until the entire Explorer is complete before executing a
test. Build the smallest complete workflow:

1.  Create a project.
2.  Enter a target URL.
3.  Open a browser.
4.  Discover one page.
5.  Generate one test.
6.  Execute it.
7.  Capture a screenshot.
8.  Show a result.

Once that workflow is stable, expand the discovery and test
capabilities.

### Suggested milestone sequence

**Milestone A --- One page can be discovered.**

**Milestone B --- One structured test can be generated.**

**Milestone C --- One test can execute and pass or fail
deterministically.**

**Milestone D --- One failure can produce a complete evidence package.**

**Milestone E --- One finding can become an assigned ticket.**

**Milestone F --- One fixed defect can be automatically retested.**

At Milestone F, TestPilot has demonstrated its core value proposition
end to end.

------------------------------------------------------------------------

# PART XII --- DEFINITION OF DONE

A feature is complete only when:

-   It has defined requirements.
-   It has an implementation.
-   It has error handling.
-   It has permission checks.
-   It has tests.
-   It has loading, empty, and failure states.
-   It has logs where appropriate.
-   It has documentation.
-   It has been tested in the integrated environment.

A scan is complete only when:

-   Its scope is known.
-   Its policy is recorded.
-   Its stages are recorded.
-   Its tests have explicit outcomes.
-   Findings have evidence.
-   Artifacts are stored.
-   Its summary is generated.
-   Its limitations are stated.
-   The scan is available in history.

A finding is complete only when:

-   It is linked to the scan or execution.
-   It contains an understandable description.
-   Its evidence is available.
-   Its confidence is recorded.
-   Its status is clear.
-   It can be reviewed or assigned.
-   Its history is preserved.

------------------------------------------------------------------------

# FINAL PRODUCT DIRECTION

TestPilot AI should be built around one central workflow:

**Discover → Understand → Plan → Execute → Verify → Investigate → Report
→ Assign → Retest**

The platform should not depend on an AI model being correct every time.
It should be designed so that AI adds intelligence, while the underlying
software provides control, reproducibility, validation, security, and
evidence.

The MVP is not the entire vision. The MVP is the first reliable
end-to-end version of that workflow.

Build that foundation well, and the future capabilities---security
scanning, API testing, change-aware regression, ticket integrations,
team analytics, and advanced autonomous testing---can be added without
turning the project into an unmanageable codebase.

------------------------------------------------------------------------

## Immediate Next Steps

Before coding:

1.  Finalize the MVP feature list.
2.  Define the system architecture and component boundaries.
3.  Design the database schema and relationships.
4.  Define the test case and action schemas.
5.  Define the scan policy and safety model.
6.  Design the repository structure.
7.  Create a controlled demo application with known defects.
8.  Set up Docker Compose.
9.  Implement the first end-to-end vertical slice.

**The first milestone is not a beautiful dashboard. It is a system that
can discover a page, generate a test, execute it, verify the result, and
capture evidence.**

Once that works, every additional module has a solid foundation.
