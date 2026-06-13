# Tellers Network CLI Specifications

Setup this repository as an collection of tools inside a single CLI. Each tool can be invoked by `tlnw-tools <tool>` syntax.
The 1st tool is generate-image. There are 2 different implementations @expertlinkedin/generate-illustrations.py and @tellstory/generate_story_illustrations.py . Inspect them and create an `generate-image` module with the following artifacts:
- SPECS.md

The repo itself must be publishable to pypi. Versioning must be consistent and updatable via configuration files rather than codes.

Each tool itself is an independent Python package downloadable from PyPI. The tools are registered in a `tools.yml` file within the CLI. By default, no version is associated with the tool - use the latest version available. When invoked, the CLI will download the tool's package automatically or use an version existing in the system, then execute it, passing all cmd arguments to the tool's executable.

The CLI provides the following common options:
- `--help`: syntax description and available tool availables
- `--debug`: debug-level logging

All python files must have passing unit tests

Log **this** prompt into a SPECS.md file in the root folder. 
Create README.md, CHANGELOG.md too.
