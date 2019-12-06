Plugin Schemas
==============

Plugins define their desired form of their config using draft 4 of the
`JSON Schema <http://json-schema.org>`_ specification. The schema for a plugin
should be stored ``schema`` attribute of the plugin class. The schema is used
for several things including:

* Validating the config format matches what is expected
* Set defaults in the config that user did not provide
* Generating a form for the webui config editor

You can run the `test_config_schema.py` test in the suite to test the validity
of your plugin's schema. The error messages it produces may help you fix your
schema if you are having trouble. Note that this doesn't check the schema
validates what you want, just that it is a valid json schema.

The following list of keywords is not exhaustive, just a general primer, as
well as some FlexGet specific notes. The JSON schema spec should be referred to
for more details, or if a keyword is not covered here. Take not that our
schemas will be defined as python objects equivalent to parsed JSON. The full
list of valid keywords can be found in section 5 of the `validaton spec`_.

.. _validaton spec: http://json-schema.org/latest/json-schema-validation.html

Keywords
--------

``type``
^^^^^^^^

The ``type`` keyword specifies what primitive data type a given item in the
config should have. It can either be a single type, or a list of types. The
``type`` keyword should be specified in almost every schema, even when other
keywords are included which might make it redundant, as it is used to select
which branch should be chosen to show errors when the config can take multiple
forms. The types in JSON schema are slightly different than their python
counterparts. Here are the valid options, along with the python types they map
to:

================  ===========
JSON Schema type  Python type
================  ===========
string            unicode
boolean           bool
number            float
integer           int
array             list
object            dict
null              type(None)
================  ===========

``items``
^^^^^^^^^

This keyword is used to validate the content of a list ('array' in json schema
terms.) Its value should be a schema that each item in the list matches.

The following example describes a list of strings::

    {"type": "array", "items": {"type": "string"}}

``properties``
^^^^^^^^^^^^^^

This keyword is used to validate the values in a dictionary. It should be a
dictionary mapping from key name, to schema which validates the value for that
key.

The following example describes a dictionary with two keys, 'a', and 'b', both
of which must be integers (``additionalProperties`` will be explained below)::

    {
        "type": "object",
        "properties": {
            "a": {"type": "integer"},
            "b": {"type": "integer"}
        },
        "additionalProperties": False
    }

``additionalProperties``
^^^^^^^^^^^^^^^^^^^^^^^^

By default, JSON schema will allow any keys which are not defined in the
``properties`` dictionary without validation. To disallow extra keys, use the
``{"additionalProperties": False}`` form, as in the above example. This should
be used in almost every schema which defines the ``properties`` keyword. The
other use for this keyword is if you want to allow a dictionary with any keys,
but still require the values to match a schema.

The following example allows a dictionary with any keys, as long as the values
are strings::

    {
        "type": "object",
        "additionalProperties": {"type": "string"}
    }

``oneOf`` and ``anyOf``
^^^^^^^^^^^^^^^^^^^^^^^

These keywords are used when the config could take more than one format. The
value should be a list of schemas one of which, or any of which must match,
depending on the keyword used.

The following schema will allow either a boolean or an integer::

    {"oneOf": [{"type": "boolean"}, {"type": "integer"}]}

``format``
^^^^^^^^^^

The format keyword is used to make sure a string follows a specific format.
Here are the format validators included with FlexGet, along with what they
validate::

email
    email addresses

quality
    FlexGet quality, e.g. ``720p hdtv``

quality_requirements
    FlexGet quality requirements specifier, e.g. ``720p-1080p hdtv+``

interval
    A text representation of a time interval, e.g. ``3 hours``, ``10 minutes``
    Intervals in this format can be parsed to a :class:`datetime.timedelta` object using the utility function
    :func:`flexget.utils.tools.parse_timedelta`

regex
    valid regular expression

file
    an existing file on the local filesystem

path
    an existing directory on the local filesystem (if path contains Jinja, only
    validates path exists before first Jinja component of path)

The following schema checks for valid regex::

    {"type": "string", "format": "regex"}

``$ref``
^^^^^^^^

This keyword is used to reference a schema defined somewhere else. The most
common use of this keyword will be to allow a plugin to take other plugins
within their configuration. It takes the form of an URI reference. The fragment
part should be a `JSON pointer`_ to a section of the referenced document. If
*only* a fragment portion of an URI is specified, the base document is assumed
to be the current schema.

.. _JSON pointer: http://tools.ietf.org/html/draft-ietf-appsawg-json-pointer-07

The following schema allows a dictionary with keys equal to plugin names (which
have input phase handlers,) and values equal to the configuration required for
that plugin. We don't actually define the validation keywords here, we are just
referencing an already built schema which has been registered by some other
plugin or component of FlexGet::

    {"$ref": "/schema/plugins?phase=input"}

``definitions``
^^^^^^^^^^^^^^^

This keyword does not affect validation, it is merely used to define parts of
your schema that may get re-used in more than one place. It should be in the
form of a dictionary mapping arbitrary names to a schema.

The following schema defines a definition called posNumber, and references it
from two places within the schema::

    {
        "type": "object",
        "properties": {
            "numberA": {"$ref": "#/definitions/posNumber"},
            "numberB": {"$ref": "#/definitions/posNumber"}
        },
        "additionalProperties": False,
        "definitions": {
            "posNumber": {"type": "number", "minimum": 0}
        }
    }

The ``$ref`` used in this example included a fragment part of an URI only, so
it references this schema, and drills down into it with a JSON pointer.

``title`` and ``description``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``title`` and ``description`` keywords are not used during validation at
all. If provided, they will be used to display more information to the user
in the configuration editor.

``default``
^^^^^^^^^^^

The ``default`` keyword is not used during validation either. It will be used
to fill in default values for properties in the config that the user has not
provided. This will be done automatically before the parsed config is passed
to the plugin.

``not``
^^^^^^^

The ``not`` keyword will allow you to negate a specific schema. This is especially useful when wanting to create
mutually exclusive properties or groups::

    {
        "type": "object",
        "properties": {
            "this": {"type": "string"},
            "that": {"type": "string"}
        },
        "not": {
            "required": ["this", "that"]
        },
        "error_not": "Can not use both 'this' and 'that'
    }

Another more complex example::

    {
        "type": "object",
        "properties": {
            "this": {"type": "string"},
            "that": {"type": "string"},
            "those": {"type": "string"}
        },
        "not": {
            "anyOf": [
                "required": ["this", "that"],
                "required": ["this", "those"],
                "required": ["that", "those"]
             ]
        },
        "error_not": "Can only use one of 'this', 'that' or 'those'
    }

``dependencies``
^^^^^^^^^^^^^^^^

``dependencies`` are used to link a property to one or more other property, raising a validation error if not all
dependencies have been met::

     {
        "type": "object",
        "properties": {
            "this": {"type": "string"},
            "that": {"type": "string"},
            "another" {"type": "string"}
        },
        "dependencies": {
            "this": ["that"]
        }
     }

