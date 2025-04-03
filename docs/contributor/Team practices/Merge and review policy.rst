=======================
Merge and review policy
=======================

Our policy for merging and reviewing describes how we review one another's work, and when we allow
others to merge changes into our main codebase. It tries to balance a few goals:

- Iterate on PRs and merge them relatively quickly, so that we reduce the debt associated with
  long-lasting PRs.
- Give enough time for others to provide their input and guide the PR itself, and to ensure that
  we aren't creating a problem with the PR.
- Value iterative improvement over creating the perfect Pull Request, so that we do not burden
  contributors with cumbersome discussion and minor revision requests.
- Recognize that we all have limited time and resources, and so cannot guarantee a full quality
  assurance process each time.
- Give general preference to the opinions of maintainers of projects in the FlexGet ecosystem, as
  a key stakeholder community of this tool.

We follow these guidelines to achieve these goals:

- Assume that all maintainers are acting in good faith and will use their best judgment to make
  decisions in the best interests of the repository.
- We can and will make mistakes, so encourage best practices in testing and documentation to
  guard against this.
- It's important to share information, so give your best effort at telling others about the work
  that you're doing.
- It's best to discuss and agree on important decisions at a high level before implementation, so
  give the best effort at providing time and invitation for others to provide feedback.

Policy for moderate changes
===========================

These are changes that make modest changes to new or existing functionality, but that aren't going
to significantly change the default behavior of the tool, user configuration, etc.
This is the majority of changes that we make.

PRs should:

- Refer to (and ideally close) an issue that describes the problem this change is solving.
- Have relevant testing and documentation coverage.

They can be merged when the above conditions are met, and one of these things happens:

- The PR has at least one approval from a core maintainer that isn't the PR author
- The PR author has signaled their intent to merge unless there are objections, and 48 hours have
  passed since that comment.

Policy for major new features and breaking changes
==================================================

These are changes that significantly alter the experience of the user, or that add significant
complexity to the codebase.

All the above, but PRs **must** have approval from at least one other core maintainer before
merging. In addition, the PR author should put extra effort into ensuring that the relevant
stakeholders are notified about a change, so they can gauge its impact and provide feedback.

Policy For minor changes and bugfixes
=====================================

These are small changes that might be noticeable to the user, but in a way that is clearly an
improvement. They generally shouldn't touch too many lines of code.

Update the relevant tests and documentation, but PR authors are welcome to self-merge whenever
they like without PR approval.
