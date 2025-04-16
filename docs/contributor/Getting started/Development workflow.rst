.. highlight:: console

====================
Development workflow
====================

You already have your own forked copy of the FlexGet repository, have configured
Git, and have linked the upstream repository as explained in
:ref:`linking to upstream`. What is described below is a recommended workflow
with Git.

Basic workflow
##############

In short:

1. Start a new *feature branch* for each set of edits that you do.
   See :ref:`below <Making a new feature branch>`.

2. Hack away! See :ref:`below <The editing workflow>`

3. When finished:

   - *Contributors*: push your feature branch to your own Github repo,
     then :ref:`create a pull request <asking for merging>`, fix findings of
     various linters and checks, and finally work through code review.

   - *Core developers*: If you want to push changes without
     further review, see the notes :ref:`below <pushing to main>`.

This way of working helps to keep work well organized and the history
as clear as possible.

.. _Making a new feature branch:

Making a new feature branch
===========================

First, fetch new commits from the ``upstream`` repository::

   $ git fetch upstream

Then, create a new branch based on the ``develop`` branch of the upstream
repository::

   $ git checkout -b my-new-feature upstream/develop

.. _The editing workflow:

The editing workflow
====================

Overview
--------

::

   $ git status # Optional
   $ git diff # Optional
   $ git add modified_file
   $ git commit
   # push the branch to your own Github repo
   $ git push origin my-new-feature

In more detail
--------------

#. Make some changes. When you feel that you've made a complete, working set
   of related changes, move on to the next steps.

#. Optional: Check which files have changed with ``git status``. You'll see a
   listing like this one:

   .. code:: text

     # On branch my-new-feature
     # Changed but not updated:
     #   (use "git add <file>..." to update what will be committed)
     #   (use "git checkout -- <file>..." to discard changes in working directory)
     #
     #	modified:   README
     #
     # Untracked files:
     #   (use "git add <file>..." to include in what will be committed)
     #
     #	INSTALL
     no changes added to commit (use "git add" and/or "git commit -a")

#. Optional: Compare the changes with the previous version using with ``git
   diff``. This brings up a simple text browser interface that
   highlights the difference between your files and the previous version.

#. Add any relevant modified or new files using  ``git add modified_file``.
   This puts the files into a staging area, which is a queue
   of files that will be added to your next commit. Only add files that have
   related, complete changes. Leave files with unfinished changes for later
   commits.

#. To commit the staged files into the local copy of your repo, do ``git
   commit``. At this point, a text editor will open up to allow you to write a
   commit message. Read the :ref:`commit message
   section<Writing the commit message>` to be sure that you are writing a
   properly formatted and sufficiently detailed commit message. After saving
   your message and closing the editor, your commit will be saved. For trivial
   commits, a short commit message can be passed in through the command line
   using the ``-m`` flag. For example, ``git commit -am "fix(core): Some message"``.

   In some cases, you will see this form of the commit command: ``git commit
   -a``. The extra ``-a`` flag automatically commits all modified files and
   removes all deleted files. This can save you some typing of numerous ``git
   add`` commands; however, it can add unwanted changes to a commit if you're
   not careful.

#. Push the changes to your fork on GitHub::

      $ git push origin my-new-feature

.. note::

   Assuming you have followed the instructions in these pages, git will create
   a default link to your GitHub repo called ``origin``.  You
   can ensure that the link to origin is permanently set by using the
   ``--set-upstream`` option::

      $ git push --set-upstream origin my-new-feature

   From now on, ``git`` will know that ``my-new-feature`` is related to the
   ``my-new-feature`` branch in your own GitHub repo. Subsequent push calls
   are then simplified to the following::

      $ git push

   You have to use ``--set-upstream`` for each new branch that you create.


It may be the case that while you were working on your edits, new commits have
been added to ``upstream`` that affect your work. In this case, follow the
:ref:`Rebasing on main` section of this document to apply those changes to
your branch.

.. _Writing the commit message:

Writing the commit message
--------------------------

Commit messages should be clear and follow a few basic rules.  Example::

   feat(plugin): add telegram notifier

Describing the motivation for a change, the nature of a bug for bug fixes or
some details on what an enhancement does are also good to include in a commit
message.  Messages should be understandable without looking at the code
changes.  A commit message like ``fix(api): fixed another one`` is an example of
what not to do; the reader has to go look for context elsewhere.

You can learn about all the specifications at `Conventional Commits
<https://www.conventionalcommits.org>`__.

.. _asking for merging:

Asking for your changes to be merged with the main repo
=======================================================

When you feel your work is finished, you can create a pull request (PR).

We review pull requests as soon as we can, typically within a week. If you get
no review comments within two weeks, feel free to ask for feedback by
adding a comment on your PR (this will notify maintainers).

.. _Rebasing on main:

Rebasing on main
================

This updates your feature branch with changes from the upstream FlexGet
GitHub repo. If you do not absolutely need to do this, try to avoid doing
it, except perhaps when you are finished. The first step will be to update
the remote repository with new commits from upstream::

    $ git fetch upstream

Next, you need to update the feature branch::

   # go to the feature branch
   $ git checkout my-new-feature
   # make a backup in case you mess up
   $ git branch tmp my-new-feature
   # rebase on upstream develop branch
   $ git rebase upstream/develop

If you have made changes to files that have changed also upstream,
this may generate merge conflicts that you need to resolve. See
:ref:`below<Recovering from mess-ups>` for help in this case.

Finally, remove the backup branch upon a successful rebase::

   $ git branch -D tmp

.. note::

   Rebasing on develop is preferred over merging upstream back to your
   branch. Using ``git merge`` and ``git pull`` is discouraged when
   working on feature branches.

.. _Recovering from mess-ups:

Recovering from mess-ups
========================

Sometimes, you mess up merges or rebases. Luckily, in Git it is
relatively straightforward to recover from such mistakes.

If you mess up during a rebase::

   $ git rebase --abort

If you notice you messed up after the rebase::

   # reset branch back to the saved point
   $ git reset --hard tmp

If you forgot to make a backup branch::

   # look at the reflog of the branch
   $ git reflog show my-feature-branch

   8630830 my-feature-branch@{0}: commit: BUG: io: close file handles immediately
   278dd2a my-feature-branch@{1}: rebase finished: refs/heads/my-feature-branch onto 11ee694744f2552d
   26aa21a my-feature-branch@{2}: commit: BUG: lib: make seek_gzip_factory not leak gzip obj
   ...

   # reset the branch to where it was before the botched rebase
   $ git reset --hard my-feature-branch@{2}

If you didn't actually mess up but there are merge conflicts, you need to
resolve those.


Additional things you might want to do
######################################

Rewriting commit history
========================

.. note::

   Do this only for your own feature branches.

There's an embarrassing typo in a commit you made? Or perhaps you
made several false starts you would like the posterity not to see.

This can be done via *interactive rebasing*.

Suppose that the commit history looks like this::

    $ git log --oneline
    eadc391 Fix some remaining bugs
    a815645 Modify it so that it works
    2dec1ac Fix a few bugs + disable
    13d7934 First implementation
    6ad92e5 * masked is now an instance of a new object, MaskedConstant
    ...

and ``6ad92e5`` is the last commit in the ``develop`` branch. Suppose we
want to make the following changes:

* Rewrite the commit message for ``13d7934`` to something more sensible.
* Combine the commits ``2dec1ac``, ``a815645``, ``eadc391`` into a single one.

We do as follows::

    # make a backup of the current state
    $ git branch tmp HEAD
    # interactive rebase
    $ git rebase -i 6ad92e5

This will open an editor with the following text in it:

.. code:: text

    pick 13d7934 First implementation
    pick 2dec1ac Fix a few bugs + disable
    pick a815645 Modify it so that it works
    pick eadc391 Fix some remaining bugs

    # Rebase 6ad92e5..eadc391 onto 6ad92e5
    #
    # Commands:
    #  p, pick = use commit
    #  r, reword = use commit, but edit the commit message
    #  e, edit = use commit, but stop for amending
    #  s, squash = use commit, but meld into previous commit
    #  f, fixup = like "squash", but discard this commit's log message
    #
    # If you remove a line here THAT COMMIT WILL BE LOST.
    # However, if you remove everything, the rebase will be aborted.
    #

To achieve what we want, we will make the following changes to it::

    r 13d7934 First implementation
    pick 2dec1ac Fix a few bugs + disable
    f a815645 Modify it so that it works
    f eadc391 Fix some remaining bugs

This means that (i) we want to edit the commit message for
``13d7934``, and (ii) collapse the last three commits into one. Now we
save and quit the editor.

Git will then immediately bring up an editor for editing the commit
message. After revising it, we get the output::

    [detached HEAD 721fc64] FOO: First implementation
     2 files changed, 199 insertions(+), 66 deletions(-)
    [detached HEAD 0f22701] Fix a few bugs + disable
     1 files changed, 79 insertions(+), 61 deletions(-)
    Successfully rebased and updated refs/heads/my-feature-branch.

and the history looks now like this::

     0f22701 Fix a few bugs + disable
     721fc64 ENH: Sophisticated feature
     6ad92e5 * masked is now an instance of a new object, MaskedConstant

If it went wrong, recovery is again possible as explained :ref:`above
<Recovering from mess-ups>`.

Deleting a branch on GitHub
===========================

::

   $ git checkout develop
   # delete branch locally
   $ git branch -D my-unwanted-branch
   # delete branch on github
   $ git push origin --delete my-unwanted-branch

Several people sharing a single repository
==========================================

If you want to work on some stuff with other people, where you are all
committing into the same repository, or even the same branch, then just
share it via GitHub.

First fork Flexget into your account.

Then, go to your forked repository github page, say
``https://github.com/your-user-name/Flexget``

Click on the 'Collaborators' button in the repository settings, and
add anyone else to the repo as a collaborator.

Now all those people can do ::

   $ git clone git@github.com:your-user-name/Flexget.git

Remember that links starting with ``git@`` use the ssh protocol and are
read-write; links starting with ``git://`` are read-only.

Your collaborators can then commit directly into that repo with the
usual::

   $ git commit -am 'feat(plugin): add telegram notifier'
   $ git push origin my-feature-branch # pushes directly into your repo

Checkout changes from an existing pull request
==============================================

If you want to test the changes in a pull request or continue the work in a
new pull request, the commits are to be cloned into a local branch in your
forked repository.

First ensure your upstream points to the main repo, as from :ref:`linking to upstream`.

Then, fetch the changes and create a local branch. Assuming ``$ID`` is the pull request number
and ``$BRANCHNAME`` is the name of the *new local* branch you wish to create::

   $ git fetch upstream pull/$ID/head:$BRANCHNAME

Checkout the newly created branch::

   $ git checkout $BRANCHNAME

You now have the changes in the pull request.

Exploring your repository
=========================

To see a graphical representation of the repository branches and
commits::

   $ gitk --all

To see a linear list of commits for this branch::

   $ git log

.. _pushing to main:

Pushing changes to the main repo
================================

*Requires commit rights to the main FlexGet repo.*

When you have a set of "ready" changes in a feature branch ready for
FlexGet's ``develop`` branch, you can push them to ``upstream`` as follows:

1. First, merge or rebase on the target branch.

   a) Only a few, unrelated commits then prefer rebasing::

      $ git fetch upstream
      $ git rebase upstream/develop

      See :ref:`Rebasing on main`.

   b) If all of the commits are related, create a merge commit::

      $ git fetch upstream
      $ git merge --no-ff upstream/develop

2. Check that what you are going to push looks sensible::

   $ git log -p upstream/develop..
   $ git log --oneline --graph

3. Push to upstream::

   $ git push upstream my-feature-branch:develop

.. note::

    It's usually a good idea to use the ``-n`` flag to ``git push`` to check
    first that you're about to push the changes you want to the place you
    want.
