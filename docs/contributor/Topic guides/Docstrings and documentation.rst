.. _Docstrings and documentation:

============================
Docstrings and documentation
============================

Contributing to docstrings
==========================

.. attention::
   All docstrings must be written in reStructuredText (reST) to ensure proper rendering
   in our documentation system.

When writing or updating docstrings, please use the Sphinx-style format. Here is a basic
example of a properly formatted Sphinx-style docstring::

    def example_function(param1: int, param2: str) -> bool:
        """
        Briefly describe what the function does.

        :param param1: Description of the first parameter.
        :param param2: Description of the second parameter.
        :return: Description of the return value.
        """
        pass

Make sure your docstrings are clear, concise, and follow the project's style guidelines.

Contributing to the user wiki
=============================

`The user wiki <https://flexget.com>`__ is powered by `Wiki.js <https://js.wiki/>`__
and is open for anyone to edit. All changes are applied immediately without staff intervention.
If you come across outdated or missing information, you are encouraged to contribute by improving
the content. You can:

- Add new guides or tutorials.
- Update existing documentation with more recent information.
- Fix formatting, grammar, or inconsistencies.

To contribute, simply visit the wiki site and follow the provided editing guidelines.
Please note that editing requires signing in via GitHub or Google using OAuth.

The wiki is bi-directionally synchronized with the GitHub repository at https://github.com/Flexget/wiki.
While you may choose to submit a pull request to the GitHub repository,
the simplest and most direct way to contribute is by editing the wiki through the website.

For details related to wiki hosting and configuration, see the hosting repository at https://github.com/Flexget/wiki-hosting.

Building and contributing to the documentation
==============================================

#. To build the HTML documentation, first :ref:`install the docs dependencies
   <Installing the docs dependencies>`.

#. Enter the virtual environment:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Unix
         :sync: Unix

         .. code:: console

            $ source .venv/bin/activate

      .. tab-item:: Windows
         :sync: Windows

         .. code:: console

            $ Set-ExecutionPolicy Unrestricted -Scope CurrentUser
            $ .venv\Scripts\activate.ps1

#. Then navigate to the ``docs`` directory:

   .. code:: console

      $ cd docs

#. Finally, run:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Unix
         :sync: Unix

         .. code:: console

            $ make html

      .. tab-item:: Windows
         :sync: Windows

         .. code:: console

            $ .\make html

Built docs are at ``docs/_build/html``.

If you want to make changes, feel free to submit a pull request.
