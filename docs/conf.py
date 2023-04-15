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
    "special-members": "__await__",
}

autodoc_member_order = 'bysource'
# autodoc_typehints = "description"
autodoc_type_aliases = {
    'JsonTypeCo': 'JsonTypeCo'
}
autodoc_typehints_format = 'short' 
python_use_unqualified_type_names = True


# -- Options for HTML output -------------------------------------------------
html_theme = 'furo'
html_static_path = ['_static']
html_title = "SlyMastodon for Python"


from sphinx.ext import autodoc

class MockedClassDocumenter(autodoc.ClassDocumenter):
    def add_line(self, line: str, source: str, *lineno: int) -> None:
        if line == "   Bases: :py:class:`object`":
            return
        super().add_line(line, source, *lineno)

autodoc.ClassDocumenter = MockedClassDocumenter