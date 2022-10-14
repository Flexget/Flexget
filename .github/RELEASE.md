# Creating a Release

Currently, flexget is built nightly at as long as there are changes on the development branch.

If you have write access to this repo, you can also trigger a manual release.

To trigger a manual release:

1. Go to the [Trigger Deploy](https://github.com/Flexget/Flexget/actions/workflows/nightly.yml) workflow.
2. Click on the `Run workflow` button there.
3. Leave the default of running it from the develop branch.
4. Profit.

You should be able to navigate to the [Main Workflow](https://github.com/Flexget/Flexget/actions?query=workflow%3A%22Main+Workflow%22+event%deployment) tab in actions and see your workflow run there as well as seeing it on the [Deployments Page](https://github.com/Flexget/Flexget/deployments?environment=production#activity-log)
