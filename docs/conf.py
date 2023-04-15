# -- Project information -----------------------------------------------------
project = 'SlySerialize'
copyright = '2023, Dunkyl 🔣🔣'
author = 'Dunkyl 🔣🔣'

# -- General configuration ---------------------------------------------------
templates_path = ['_templates']
exclude_patterns = ['build', 'Thumbs.db', '.DS_Store']

extensions = [
    'myst_parser',
    'sphinxcontrib_trio',
    'sphinx_copybutton',
    'sphinxext.opengraph',
    'sphinx.ext.autodoc',
    'sphinx.ext.duration',
    # 'sphinx.ext.napoleon',
    'sphinx.ext.autosummary',
]
myst_enable_extensions = ["colon_fence"]

# napoleon_preprocess_types = True


# autoclass_content = "both"
# autosummary_generate = True

autodoc_default_options = {
    "members": True,
    "inherited-members": True,
    "private-members": False,
    "show-inheritance": False,
    "undoc-members": True,
    "member-order": "bysource",
}

autodoc_member_order = 'bysource'
# autodoc_typehints = "description"
autodoc_type_aliases = {
    "JsonScalar": "JsonScalar"
}
# autodoc_typehints_format = 'short' 
python_use_unqualified_type_names = True


# -- Options for HTML output -------------------------------------------------
html_theme = 'furo'
html_static_path = ['_static']
html_title = "SlyMastodon for Python"


from sphinx.ext import autodoc

def json_scalar_(s: str) -> str:
    return s.replace(
        "int | float | bool | str | None",
        "JsonScalar"
    )

def json_type_(s: str) -> str:
    return s.replace(
        "JsonScalar | ~collections.abc.Sequence[JsonScalar | ~collections.abc.Sequence[JsonType] | ~collections.abc.Mapping[str, JsonType]] | ~collections.abc.Mapping[str, JsonScalar | ~collections.abc.Sequence[JsonType] | ~collections.abc.Mapping[str, JsonType]]",
        "JsonType"
    )

def ref_json_type_(s: str) -> str:
    return s.replace(
        r":py:class:`int` | :py:class:`float` | :py:class:`bool` | :py:class:`str` | :py:obj:`None` | :py:class:`~collections.abc.Sequence`\ [JsonType] | :py:class:`~collections.abc.Mapping`\ [:py:class:`str`, JsonType]",
        ":py:class:`JsonType`"
    )

class MockedClassDocumenter(autodoc.ClassDocumenter):
    def add_line(self, line: str, source: str, *lineno: int) -> None:
        if line == "   Bases: :py:class:`object`":
            return
        line = ref_json_type_(line)
        super().add_line(line, source, *lineno)

class MockedMethodDocumenter(autodoc.MethodDocumenter):
    def format_signature(self, **kwargs) -> str:
        return json_type_(json_scalar_(super().format_signature(**kwargs)))
    
class MockedFnDocumenter(autodoc.FunctionDocumenter):
    def format_signature(self, **kwargs) -> str:
        return json_type_(json_scalar_(super().format_signature(**kwargs)))

autodoc.ClassDocumenter = MockedClassDocumenter
autodoc.MethodDocumenter = MockedMethodDocumenter
autodoc.FunctionDocumenter = MockedFnDocumenter