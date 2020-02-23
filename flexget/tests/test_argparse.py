from argparse import Action

from flexget.options import ArgumentParser


def test_subparser_nested_namespace():
    p = ArgumentParser()
    p.add_argument('--outer')
    p.add_subparsers(nested_namespaces=True)
    sub = p.add_subparser('sub')
    sub.add_argument('--inner')
    sub.add_subparsers()
    subsub = sub.add_subparser('subsub')
    subsub.add_argument('--innerinner')
    result = p.parse_args(['--outer', 'a', 'sub', '--inner', 'b', 'subsub', '--innerinner', 'c'])
    assert result.outer == 'a'
    # First subparser values should be nested under subparser name
    assert result.sub.inner == 'b'
    assert not hasattr(result, 'inner')
    # The second layer did not define nested_namespaces, results should be in first subparser namespace
    assert result.sub.innerinner == 'c'
    assert not hasattr(result, 'innerinner')


def test_subparser_parent_defaults():
    p = ArgumentParser()
    p.add_argument('--a')
    p.set_post_defaults(a='default')
    p.add_subparsers()
    p.add_subparser('sub')
    p.add_subparser('sub_with_default', parent_defaults={'a': 'sub_default'})
    # Make sure normal default works
    result = p.parse_args(['sub'])
    assert result.a == 'default'
    # Test subparser default
    result = p.parse_args(['sub_with_default'])
    assert result.a == 'sub_default'
    # Subparser default should not override explicit one
    result = p.parse_args(['--a', 'manual', 'sub_with_default'])
    assert result.a == 'manual'


def test_post_defaults():
    class CustomAction(Action):
        def __call__(self, parser, namespace, values, option_string=None):
            if not hasattr(namespace, 'post_set'):
                namespace.post_set = 'custom'

    p = ArgumentParser()
    p.add_argument('--post-set')
    p.add_argument('--custom', action=CustomAction, nargs=0)
    p.set_post_defaults(post_set='default')
    # Explicitly specified, no defaults should be set
    result = p.parse_args(['--post-set', 'manual'])
    assert result.post_set == 'manual'
    # Nothing supplied, should get the post set default
    result = p.parse_args([])
    assert result.post_set == 'default'
    # Custom action should be allowed to set default
    result = p.parse_args(['--custom'])
    assert result.post_set == 'custom'
