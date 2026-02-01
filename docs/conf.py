# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from pathlib import Path
import os
import sys

# Add project root to path for autodoc
sys.path.insert(0, os.path.abspath('../dyrasql-core'))

# -- Read version from VERSION file -------------------------------------------
version_file = Path(__file__).parent.parent / 'VERSION'
if version_file.exists():
    with open(version_file, 'r') as f:
        release = f.read().strip()
    version = '.'.join(release.split('.')[:2])
else:
    release = '1.0.0'
    version = '1.0'

# -- Project information -----------------------------------------------------
project = 'DyraSQL'
copyright = '2026, DyraSQL Team'
author = 'DyraSQL Team'

# -- General configuration ---------------------------------------------------
extensions = [
    'myst_parser',
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx_immaterial',
    'sphinx_copybutton',
]

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', '_templates', '.venv', 'venv']

language = 'pt_BR'

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_immaterial'
html_static_path = ['_static']

# Logo (opcional - descomente se tiver logo)
# html_logo = '_static/logo.png'

html_theme_options = {
    "palette": [
        {
            "scheme": "slate",
            "primary": "deep-purple",
            "accent": "amber",
            "toggle": {
                "icon": "material/brightness-7",
                "name": "Mudar para modo claro",
            },
        },
        {
            "scheme": "default",
            "primary": "deep-purple",
            "accent": "amber",
            "toggle": {
                "icon": "material/brightness-2",
                "name": "Mudar para modo escuro",
            },
        },
    ],
    "repo_url": "https://github.com/arihenrique/dyrasql",
    "repo_name": "arihenrique/dyrasql",
    "features": [
        "content.code.copy",
        "navigation.tabs",
        "navigation.sections",
        "navigation.top",
        "search.highlight",
        "toc.follow",
    ],
    # Versão oculta (sem dropdown ao lado do título)
    "version_dropdown": False,
}

# Copy button configuration
copybutton_prompt_text = r"\$ |>>> |In \[\d*\]: |\.\.\. "
copybutton_remove_prompts = True

# MyST parser configuration
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
