import argparse
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

from .core import process_story_folder, get_default_quality, normalize_quality_for_model

# Setup local logger
logger = logging.getLogger("tlnw-generate-image")

def main():
    # Load env variables (first local .env, then system env)
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Generate illustrations for story folders and specific scene prompt files.")
    
    # Core positional / file targets
    parser.add_argument("story_folders", nargs="*", help="Story folder paths to process.")
    parser.add_argument("--file", action="append", help="Specific prompt file(s) to process directly.")
    
    # Basename and pattern configs
    parser.add_argument("--basename", "-b", help="Custom basename for prompt files and output images (e.g., will look for <basename>-prompt.txt).")
    parser.add_argument("--file-pattern", "-p", help="File pattern to match prompt files in a folder (e.g. 'illustration-prompt-cover-*.txt').")
    
    # Model configuration
    parser.add_argument("--model", "-m", default="gpt-image-1.5", 
                        help="Image generation model to use. Defaults to 'gpt-image-1.5'. Supports dall-e-3, imagen-4-ultra, etc.")
    
    # Quality & Sizing options
    parser.add_argument("--quality", "-q", choices=["low", "medium", "high", "standard", "hd", "auto"],
                        help="Image quality. Defaults to 'medium' for GPT models and 'standard' for Gemini Imagen models.")
    parser.add_argument("--size", help="Explicit image size (e.g. 1536x1024) to override model/orientation defaults.")
    
    # Orientation options (mutually exclusive)
    orientation_group = parser.add_mutually_exclusive_group()
    orientation_group.add_argument("--landscape", action="store_true", help="Generate landscape format (1536x1024 for GPT-image, 1792x1024 for DALL-E 3).")
    orientation_group.add_argument("--portrait", action="store_true", help="Generate portrait format (1024x1536 for GPT-image, 1024x1792 for DALL-E 3).")
    
    # Reference and Output adjustments
    parser.add_argument("--reference", dest="reference_images", action="append", default=[],
                        help="Reference image path(s) to influence image edits (DALL-E only).")
    parser.add_argument("--output-prefix", dest="output_prefix", default=None,
                        help="Prefix to prepend to generated output filenames (e.g. 'podcast').")
    
    # Format and Execution behavior options
    parser.add_argument("--format", choices=["PNG", "WEBP", "JPEG", "JPG"], default="PNG", help="Image output format. Default is PNG.")
    parser.add_argument("--skip-update", "-s", action="store_true", help="Skip updating frontmatter inside the Jekyll index.md file.")
    parser.add_argument("--force", "-f", action="store_true", help="Force regeneration of illustrations even if they already exist.")
    
    # Verbose debugging
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug-level logging.")

    args = parser.parse_args()

    # Configure Logging based on Debug option
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger.setLevel(log_level)
    
    # Determine orientation string
    if args.landscape:
        orientation = "landscape"
    elif args.portrait:
        orientation = "portrait"
    else:
        orientation = "square"

    # Default quality resolving
    quality = args.quality if args.quality else get_default_quality(args.model)

    # API key environment verification based on model family
    if not args.model.startswith("imagen-"):
        # OpenAI models require OPENAI_API_KEY
        if not os.getenv("OPENAI_API_KEY"):
            print("Error: OPENAI_API_KEY environment variable not set")
            print("For local development: Create a .env file with OPENAI_API_KEY=your_key")
            sys.exit(1)
    else:
        # Google Imagen models require GEMINI_API_KEY
        if not os.getenv("GEMINI_API_KEY"):
            print("Error: GEMINI_API_KEY environment variable not set")
            print("Create a free API key at: https://aistudio.google.com/app/apikey")
            sys.exit(1)

    # Execute file-based targets if specified
    if args.file:
        logger.info("Processing %d specific file(s)...", len(args.file))
        for item in args.file:
            process_story_folder(
                item,
                model=args.model,
                quality=quality,
                orientation=orientation,
                reference_images=args.reference_images,
                output_prefix=args.output_prefix,
                size=args.size,
                skip_update=args.skip_update,
                force=args.force,
                file_pattern=args.file_pattern,
                basename=args.basename
            )

    # Execute folder-based targets if specified
    if args.story_folders:
        logger.info("Processing %d story folder(s)...", len(args.story_folders))
        for story_folder in args.story_folders:
            logger.info("Processing: %s", story_folder)
            process_story_folder(
                story_folder,
                model=args.model,
                quality=quality,
                orientation=orientation,
                reference_images=args.reference_images,
                output_prefix=args.output_prefix,
                size=args.size,
                skip_update=args.skip_update,
                force=args.force,
                file_pattern=args.file_pattern,
                basename=args.basename
            )
            
    if not args.file and not args.story_folders:
        print("Error: No files (--file) or story folders specified.")
        parser.print_help()
        sys.exit(1)

    print("\nAll tasks processed!")

if __name__ == "__main__":
    main()
