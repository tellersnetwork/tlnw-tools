# Tellers Network Image Generation Tool (`tlnw-generate-image`)

`tlnw-generate-image` is a standalone, publishable package that unifies AI image generation for stories and posts in the Tellers Network ecosystem. It supports OpenAI (DALL-E 2, DALL-E 3, and legacy `gpt-image-1.5`) as well as Google Gemini Imagen 4 models.

## Installation
```bash
pip install tlnw-generate-image
```

## Features
- Multi-model routing (OpenAI DALL-E 3, Google Imagen 4, etc.)
- Auto-resolution of output sizing from prompt filename trailing suffixes (e.g. `-1536x1024.txt`)
- Prepending of `illustration-master-prompt.txt` to specific scene prompts
- Automatic WebP conversion and optimization
- Automated Jekyll/Hugo frontmatter images block updating

## Usage
Generate illustration for a story folder:
```bash
generate-image /path/to/story_folder --model dall-e-3
```

Process specific prompt files:
```bash
generate-image --file /path/to/prompt-1536x1024.txt --model imagen-4-ultra
```
