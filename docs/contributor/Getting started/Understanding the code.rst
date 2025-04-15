======================
Understanding the code
======================

The best strategy to better understand the code base is to pick something you want to change and
start reading the code to figure out how it works. When in doubt, you can ask questions on GitHub
Discussions. It is perfectly okay if your pull requests aren’t perfect, the community is always
happy to help. As a volunteer project, things do sometimes get dropped and it’s totally fine to
ping us if something has sat without a response for about two to four weeks.

So go ahead and pick something that annoys or confuses you about FlexGet, experiment with the code,
hang around for discussions or go through the reference documents to try to fix it. Things will
fall in place and soon you’ll have a pretty good understanding of the project as a whole. Good
Luck!

Our development stack
=====================

- Our package manager of choice is ``uv``. ``uv`` is a high-performance package manager that
  ensures fast, reliable, and deterministic dependency management.

- We use ``Ruff`` for code linting and formatting. ``Ruff`` is a lightning-fast linter and
  formatter that enforces consistent and clean Python code.

- Our test framework is ``pytest``. ``pytest`` offers a powerful, flexible, and user-friendly
  approach to writing and executing tests.

- ``FlexGet``'s web UI is implemented using React. Its source code is available at https://github.com/Flexget/webui.
  ``React`` is a modern JavaScript library for creating dynamic, responsive, and interactive
  user interfaces.

Libraries we use
================

To fully understand the code, you may need to familiarize yourself with our dependencies.
Below are the main dependencies we use, with all dependencies listed in ``pyproject.toml``.

Core dependencies
-----------------

- **SQLAlchemy** – A SQL toolkit and Object-Relational Mapper (ORM) for Python, providing
  efficient and database-agnostic interaction with relational databases.
- **BeautifulSoup** – A library for parsing and extracting data from HTML and XML files,
  often used for web scraping.
- **Feedparser** – A library for parsing RSS and Atom feeds, enabling easy extraction of news
  or blog content.
- **Python-Requests** – A user-friendly library for making HTTP requests, commonly used for
  fetching data from web APIs.
- **Jinja2** – A templating engine that allows dynamic rendering of HTML or other text-based
  formats, often used in web applications.
- **PyYAML** – A library for parsing and generating YAML files, frequently used for configuration
  files.
- **jsonschema** – A library for validating JSON data structures against predefined schemas,
  ensuring data integrity.

HTTPServer dependencies
-----------------------

- **Flask** – A lightweight web framework for building web applications and APIs.
- **Jinja2** – Used as Flask’s default templating engine to render dynamic HTML content.
- **CherryPy** – A minimalist web framework that provides a built-in HTTP server, often used for
  lightweight and standalone web applications.
