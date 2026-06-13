# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-06-13

### Added
- Standardized, publishable dynamic CLI engine `tlnw-tools` with support for dynamic tool downloading, updating, and executing.
- Unified configuration structure `tools.yml` with dual-mode execution (`inprocess_import` and `subprocess`).
- `generate-image` package that integrates, refactors, and unifies both `expertlinkedin` and `tellstory` image/illustration generators.
- Verbose debug logging, error handling, and robust OpenAI / Google Gemini Imagen 4 client pipelines.
- Pytest suite covering dynamic tool loading and quality/size normalization logic.
- Verbatim prompt logging in `SPECS.md` and basic project documentations (`README.md`, `CHANGELOG.md`).
