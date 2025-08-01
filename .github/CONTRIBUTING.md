# Feature requests

Use GitHub issues for feature requests.

# Issues

Before submitting an issue, make sure you:

- Are running the latest version of FlexGet (check `flexget --version`)
- Check the [upgrade actions](https://flexget.com/UpgradeActions) after updating to a major or minor version.
- Check if there is already an issue open about the problem.
- Fully describe the problem, explain what you expected to happen.
- Include the relevant config of the task having the trouble. (Remember to censor private info though.)
- Include log segments (especially if there are tracebacks.) Remember to censor private info from these as well.
  Sometimes debug logs may be needed as well `flexget --debug execute --tasks my_problem_task`
- Surround your config and log segments with 3 backticks ` ``` ` so that they are made into proper code blocks:

        ```
        <config or log here>
        ```

# Pull Requests

For help, see GitHub's guides on [forking a repo](https://help.github.com/articles/fork-a-repo/) and
[pull requests.](https://help.github.com/articles/using-pull-requests/)

When submitting pull requests:

- Submit PRs against the [develop](https://github.com/Flexget/Flexget/tree/develop) branch.
- Explain in your PR the bug you are fixing or feature you are adding. Reference issue numbers if relevant.
- If config changes are needed, mention those as well. They will be needed for the
  [UpgradeActions](http://flexget.com/UpgradeActions) page upon merging anyway.
- Make separate PRs for separate ideas. The smaller each PR is the easier it is to get it reviewed and merged.
  You don't want a bugfix to get held up by a new feature you also added.

# Commit messages

If you want a commit to automatically create an entry in the [changelog](http://flexget.com/ChangeLog) you need to
prefix with with square brackets and one of the following tags, followed by plugin name:

- `add`, `added` or `feature` for the `Added` category
- `change`, `changed` or `update` for the `Changed` category
- `fix` or `fixed` for the `Fixed` category
- `deprecate` or `deprecated` for the `Deprecated` category
- `remove` or `removed` for the `Removed` category.

Example:  
`[add] pending_approval - Pending approval plugin, CLI & API`

Note that the changelog can always be updated manually, but sticking to this structure allows for easier generation.

# Wiki

Updating the wiki is also a valuable way to contribute. The wiki can be found at <http://flexget.com>
