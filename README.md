# Tellers Network Tools CLI (`tlnw-tools`)

`tlnw-tools` is a modular, dynamic command-line interface (CLI) to manage and run a collection of independent tools in the Tellers Network ecosystem. Each tool is developed as a separate package published to PyPI and registered in `tools.yml`. When invoked, the main CLI dynamically verifies, downloads (if missing), and executes the tool either in-process (by default) or as a subprocess.

## Features
- **Dynamic Tool Execution**: Run tools registered in `tools.yml` directly using `tlnw-tools <tool>`.
- **Automatic Packaging Management**: Automatically downloads, installs, or updates tools dynamically via `pip` on invocation.
- **Configurable Isolation**: Supports executing tools either via in-process module importing or subprocess delegation, configurable on a per-tool basis in `tools.yml`.
- **Consistent CLI**: Standard common arguments like `--help` and `--debug`.

## Installation
You can install the main CLI via PyPI:
```bash
pip install tlnw-tools
```

## Configuration (`tools.yml`)
The main CLI registry lies in `tools.yml` located in the root of the project (or can be customized):
```yaml
version: 0.1.0
description: "A collection of tools for various tasks and functionalities in the Tellers Network ecosystem."
tools:
  - name: "generate-image"
    package: "tlnw-generate-image"
    execution_mode: "inprocess_import"
    module: "tlnw_generate_image.cli"
    entry_point: "main"
    description: "Generate images and illustrations with OpenAI and Gemini models."
```

## Commands
```bash
# General help
tlnw-tools --help

# Running a registered tool (e.g., generate-image)
tlnw-tools generate-image --help
```

---

# Tool: `generate-image`

`generate-image` is the first unified tool package. It integrates and harmonizes image generation capabilities for story folders and specific scenes across both OpenAI (DALL-E 2/3, `gpt-image-1.5`) and Google Imagen 4.

### Usage
```bash
tlnw-tools generate-image <story_folders> [options]
```

### Options
- `--model <model>`: Specify model to use. Defaults to `gpt-image-1.5`. Available models: `dall-e-3`, `gpt-image-1.5`, `imagen-4`, etc.
- `--quality <quality>`: Normalize quality across OpenAI and Gemini. Choices: `low`, `medium`, `high`, `standard`, `hd`, `auto`.
- `--landscape` / `--portrait`: Control dimensions. Defaults to square (1024x1024).
- `--size`: Manually specify dimensions (e.g., `1024x1024`).
- `--reference`: Supply reference images.
- `--output-prefix`: Prepend a custom prefix to generated files.
- `--skip-update`: Avoid updating the Jekyll/Hugo `index.md` frontmatter.
