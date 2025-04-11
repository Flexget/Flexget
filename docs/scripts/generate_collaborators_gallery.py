"""Uses the GitHub API to list a gallery of all people with direct access to the repository."""

import json
import shlex
from pathlib import Path
from subprocess import run

from yaml import dump

COLLABORATORS_API = '/repos/flexget/flexget/collaborators?affiliation=direct'

print("Grabbing latest collaborators with GitHub API via GitHub's CLI...")
out = run(shlex.split(f'gh api {COLLABORATORS_API}'), capture_output=True, check=False)
collaborators = json.loads(out.stdout.decode())
path_docs_source = Path(__file__).parents[1]
path_collaborators = path_docs_source / '_static/collaborators.yaml'
collaborator_yaml = [
    {
        'header': f'@{collaborator["login"]}',
        'image': f'https://avatars.githubusercontent.com/u/{collaborator["id"]}',
        'link': collaborator['html_url'],
    }
    for collaborator in collaborators
]
print('Writing collaborator YAML to disk...')
path_collaborators.touch()
with path_collaborators.open('w+') as ff:
    dump(collaborator_yaml, ff)
print('Finished!')
