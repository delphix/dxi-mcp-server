# PERFORCE® DELPHIX - CONTRIBUTING

Contributing
Fork the project.
Make your bug fix or new feature.
Add tests for your code.
Send a pull request.
Contributions must be signed as User Name <user@email.com>. Make sure to set up Git with your user name and email address. All pull requests should target the `main` branch.

Contributor Agreement
All contributors are required to sign the Delphix Contributor agreement prior to contributing code to an open source repository. 
This CLA is the entire agreement between the parties, and supersedes any and all prior agreements, understandings or communications, written or oral, between the parties relating to the subject matter hereof.  This Agreement, and any amendments thereto, may be executed in one or more counterparts each of which will be deemed an original, but all of which together will constitute one and the same instrument.  The parties may transmit their signatures via scanned PDF, e-signature, or other electronic signature tools with the same effect as if the parties had provided each other with original signatures. You can refer below review process for more details.

Code of Conduct
This project operates under the Delphix Code of Conduct. By participating in this project you agree to abide by its terms.

## Our Review Process

When you submit a pull request, our team follows this internal process:

1.  **Fork and Test**: We fork your branch to run it through our internal, comprehensive testing suite.
2.  **JIRA Ticket Creation**: A JIRA ticket is created to track the contribution through our internal workflows.
3.  **Merge to Main**: Once your changes pass all tests and reviews, they are merged into the `main` branch by a Delphix team member.
4.  **PR Closure**: After a successful merge, we will close your original pull request.

We appreciate your contribution and patience during this process!

## Acceptance Criteria Format

All non-trivial stories and tasks (story points ≥ 2) must include at least one acceptance criterion written as a testable Given/When/Then assertion. Acceptance criteria belong both in the Jira ticket description and in the `## Acceptance Criteria (test assertions)` section of the GitHub PR template.

**Format**:

```
Given [precondition or system state],
When [action or event],
Then [observable expected outcome].
```

**Project-specific example** (checkbox format — use this style in your PRs):

- [ ] AC-1: Given `DCT_TOOLSET=auto` and no toolset is currently enabled, when `enable_toolset("self_service")` is called, then the MCP client's tool list includes `vdb_tool` within one round-trip notification and `list_available_toolsets` still returns the full toolset catalogue.

Use concrete, observable outcomes — "the response body contains `status=enabled`" is testable; "it works correctly" is not. Reference real domain concepts (`DCT_TOOLSET`, `vdb_tool`, `confirmation_required`, toolset names) rather than generic placeholders.

## Specification Docs for Larger Tickets

For substantial tickets (story points ≥ 5), the preferred path is to generate the full specification set — vision, functional (with numbered `FR-*` requirements), design, and test plan — using the `dataconnectors-and-integrations` `feature-implement` skill rather than hand-writing the spec:

```
/feature-implement <TICKET-ID>
```

This produces `docs/<TICKET-ID>/<TICKET-ID>-functional.md` (plus vision, design, and test-plan docs) in which the `FR-*` requirements and Given/When/Then acceptance criteria become the contract the implementation is built and verified against. Smaller tickets still need acceptance criteria in the format above, but do not require the full spec-doc set.

## AI Pre-Review Expectation

Before requesting human review on any PR, contributors are expected to run the AI pre-review step using the `dataconnectors-and-integrations` review skill:

```
/review
```

Paste the `/review` output directly into the PR description (or attach it as a PR comment) so that human reviewers can see which findings were already surfaced and addressed. This is not a gate — it is a quality aid. If the `/review` output is empty or not applicable (e.g., the change is documentation-only), note that in the PR Checklist item.

The review skill is available via the `dataconnectors-and-integrations` Claude Code plugin. See the plugin documentation for setup if you have not yet installed it.