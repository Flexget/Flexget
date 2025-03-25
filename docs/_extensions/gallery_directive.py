"""A directive to generate a gallery of images from structured data.

Generating a gallery of images that are all the same size is a common
pattern in documentation, and this can be cumbersome if the gallery is
generated programmatically. This directive wraps this particular use-case
in a helper-directive to generate it with a single YAML configuration file.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective
from yaml import safe_load

if TYPE_CHECKING:
    from sphinx.application import Sphinx

logger = logging.getLogger(__name__)


class GalleryGridDirective(SphinxDirective):
    """A directive to show a gallery of images and links in a Bootstrap grid.

    The grid can be generated from a YAML file that contains a list of items, or
    from the content of the directive (also formatted in YAML). Use the parameter
    "class-card" to add an additional CSS class to all cards. When specifying the grid
    items, you can use all parameters from "grid-item-card" directive to customize
    individual cards + ["image", "header", "content", "title"].
    """

    name = 'gallery-grid'
    has_content = True
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec: ClassVar[dict[str, Any]] = {
        # A class to be added to the resulting container
        'grid-columns': directives.unchanged,
        'class-container': directives.unchanged,
        'class-card': directives.unchanged,
    }

    def run(self) -> list[nodes.Node]:
        """Create the gallery grid."""
        if self.arguments:
            # If an argument is given, assume it's a path to a YAML file
            # Parse it and load it into the directive content
            path_data_rel = Path(self.arguments[0])
            path_doc, _ = self.get_source_info()
            path_doc = Path(path_doc).parent
            path_data = (path_doc / path_data_rel).resolve()
            if not path_data.exists():
                logger.info('Could not find grid data at %s.', path_data)
                nodes.text('No grid data found at {path_data}.')
                return None
            yaml_string = path_data.read_text()
        else:
            yaml_string = '\n'.join(self.content)

        # Use all the element with an img-bottom key as sites to show
        # and generate a card item for each of them
        grid_items = []
        for item in safe_load(yaml_string):
            # remove parameters that are not needed for the card options
            title = item.pop('title', '')

            # build the content of the card using some extra parameters
            header = (
                [f'      {item.pop("header")}', '', '      ^^^', ''] if 'header' in item else ['']
            )
            image = [f'      .. image:: {item.pop("image")}', ''] if 'image' in item else ['']
            content = [f'      {item.pop("content")}', ''] if 'content' in item else ['']

            # optional parameter that influence all cards
            if 'class-card' in self.options:
                item['class-card'] = self.options['class-card']

            loc_options_str = [f'      :{k}: {v}' for k, v in item.items()]
            loc_options_str.append('')

            grid_items.append(f'   .. grid-item-card:: {title}')
            grid_items += loc_options_str
            grid_items.append('')
            grid_items += header
            grid_items += image
            grid_items += content
            grid_items.append('')

        # Parse the template with Sphinx Design to create an output container
        # Prep the options for the template grid
        class_ = 'gallery-directive' + f' {self.options.get("class-container", "")}'
        options = {'gutter': 2, 'class-container': class_}
        options_str = [f'   :{k}: {v}' for k, v in options.items()]

        # Create the directive string for the grid
        grid_directive = [f'.. grid:: {self.options.get("grid-columns", "1 2 3 4")}']
        grid_directive.extend(options_str)
        grid_directive.append('')
        grid_directive.extend(grid_items)

        # Parse content as a directive so Sphinx Design processes it
        container = nodes.container()
        self.state.nested_parse(StringList(grid_directive), 0, container)

        # Sphinx Design outputs a container too, so just use that
        return [container.children[0]]


def setup(app: 'Sphinx') -> dict[str, Any]:
    """Add custom configuration to sphinx app.

    Args:
        app: the Sphinx application

    Returns:
        the 2 parallel parameters set to ``True``.

    """
    app.add_directive('gallery-grid', GalleryGridDirective)

    return {
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
