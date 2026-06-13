import logging
import os
import sys
import re
import contextlib
import base64
import subprocess
from pathlib import Path
import requests
from PIL import Image

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

logger = logging.getLogger("tlnw-generate-image")

FEATURED_WEBP_FILENAME = "featured.webp"
THUMBNAIL_WEBP_FILENAME = "thumbnail.webp"
THUMBNAIL_MAX_DIMENSION = 768
THUMBNAIL_WEBP_QUALITY = 75

def get_default_quality(model):
    """Return default quality by model family."""
    if model.startswith("imagen-"):
        return "standard"
    if model.startswith("gpt-image"):
        return "medium"
    if model == "dall-e-3":
        return "standard"
    return "standard"


def normalize_quality_for_model(model, quality):
    """Normalize cross-model quality values to model-specific acceptable values."""
    q = (quality or get_default_quality(model)).lower()

    if model.startswith("gpt-image"):
        # gpt-image quality is typically low/medium/high/auto
        mapping = {
            "standard": "medium",
            "hd": "high"
        }
        return mapping.get(q, q)

    if model == "dall-e-3":
        # dall-e-3 quality supports standard/hd
        if q in ("hd", "high"):
            return "hd"
        if q == "medium":
            return "standard"
        return "standard"

    if model.startswith("imagen-"):
        # Normalize common aliases for imagen quality-like controls
        mapping = {
            "medium": "standard",
            "hd": "high"
        }
        return mapping.get(q, q)

    return q


def _resolve_size_for_orientation(model, orientation):
    """Map a requested orientation to an OpenAI-compatible image size."""
    if orientation == "square":
        return "1024x1024"

    if model in ["dall-e-2"]:
        raise ValueError("Landscape and portrait sizes are not supported for dall-e-2")

    if model in ["dall-e-3"]:
        if orientation == "landscape":
            return "1792x1024"
        return "1024x1792"

    if orientation == "landscape":
        return "1536x1024"
    return "1024x1536"


def load_master_prompt(story_folder: Path) -> str:
    """Load the shared illustration master prompt if the story provides one."""
    master_prompt_path = story_folder / "illustration-master-prompt.txt"
    if not master_prompt_path.exists():
        return ""

    try:
        return master_prompt_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning("Failed to load master prompt from %s: %s", master_prompt_path, e)
        return ""


def combine_master_prompt(master_prompt_text: str, prompt_text: str) -> str:
    """Prepend the shared master prompt to an individual scene prompt."""
    if not master_prompt_text:
        return prompt_text

    return f"{master_prompt_text.rstrip()}\n\n{prompt_text.lstrip()}"


def generate_image_google(prompt, out_path, model="imagen-4.0-generate-001", quality="standard"):
    """Generate image using Google's Imagen 4 API via google-genai SDK."""
    if not GOOGLE_AVAILABLE:
        print("Error: google-genai not available. Install with: pip install google-genai")
        return None
    
    # Get API key from environment
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        print("Create a free API key at: https://aistudio.google.com/app/apikey")
        sys.exit(1)
    
    try:
        # Initialize client
        client = genai.Client(api_key=api_key)
        
        # Map model name aliases to full model names
        model_map = {
            "imagen-4": "imagen-4.0-generate-001",
            "imagen-4-standard": "imagen-4.0-generate-001",
            "imagen-4-0": "imagen-4.0-generate-001",
            "imagen-4-ultra": "imagen-4.0-ultra-generate-001",
            "imagen-4-0-ultra": "imagen-4.0-ultra-generate-001",
            "imagen-4-fast": "imagen-4.0-fast-generate-001",
            "imagen-4-0-fast": "imagen-4.0-fast-generate-001"
        }
        
        full_model_name = model_map.get(model, model)
        normalized_quality = normalize_quality_for_model(full_model_name, quality)

        config_kwargs = {
            "number_of_images": 1,
            "aspect_ratio": "1:1",  # Square format for book covers
            "person_generation": "allow_adult"  # Allow people in images
        }

        # Some SDK/API versions may not support explicit quality for Imagen yet.
        try:
            response = client.models.generate_images(
                model=full_model_name,
                prompt=prompt,
                config=types.GenerateImagesConfig(**{**config_kwargs, "quality": normalized_quality})
            )
        except Exception as quality_error:
            logger.debug("quality='%s' not applied for Imagen: %s. Retrying without explicit quality.", normalized_quality, quality_error)
            response = client.models.generate_images(
                model=full_model_name,
                prompt=prompt,
                config=types.GenerateImagesConfig(**config_kwargs)
            )
        
        if response.generated_images and len(response.generated_images) > 0:
            # Save the image
            generated_image = response.generated_images[0]
            generated_image.image.save(out_path)
            logger.info("Generated with Google Imagen 4: %s", out_path)
            return out_path
        else:
            logger.error("Error: No image generated from Google Imagen API")
            return None
    
    except Exception as e:
        logger.error("Error using Google Imagen API: %s", e)
        return None


def generate_image_openai(prompt, out_path, model="gpt-image-1.5", size="1024x1024", quality="medium", reference_images: list[str] | None = None):
    """Generate image using OpenAI DALL-E or GPT image models."""
    if not OPENAI_AVAILABLE:
        logger.error("Error: openai library is not installed.")
        sys.exit(1)

    api_key = os.getenv("OPENAI_API_KEY")
    logger.debug(
        "Generating image (OpenAI): out_path=%s model=%s size=%s quality=%s reference_images=%s",
        out_path, model, size, quality, reference_images or []
    )
    
    # Check for secret injection bug
    if api_key == "OPENAI_API_KEY":
        print("ERROR: SECRET INJECTION BUG DETECTED")
        print("The OPENAI_API_KEY environment variable is set to the literal string 'OPENAI_API_KEY'")
        print("instead of the actual API key value. This appears to be a GitHub Copilot secret injection bug.")
        sys.exit(1)
    
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not found")
        print("Please set your OpenAI API key.")
        sys.exit(1)
    
    if not api_key.startswith('sk-'):
        print("ERROR: Invalid OpenAI API key format")
        sys.exit(1)
    
    openai.api_key = api_key
    client = openai.OpenAI(api_key=api_key)
    normalized_quality = normalize_quality_for_model(model, quality)

    request_kwargs = {
        "model": model,
        "n": 1,
        "size": size,
    }

    if normalized_quality is not None and model not in ["dall-e-2"]:
        request_kwargs["quality"] = normalized_quality

    # Only include response_format for DALL-E models
    if model in ["dall-e-2", "dall-e-3"]:
        request_kwargs["response_format"] = "url"

    if reference_images:
        with contextlib.ExitStack() as stack:
            image_files = [stack.enter_context(Path(image_path).open("rb")) for image_path in reference_images]
            response = client.images.edit(image=image_files, prompt=prompt, **request_kwargs)
    else:
        response = client.images.generate(prompt=prompt, **request_kwargs)

    # Robust response handling for both url and b64_json
    def get_field(obj, field):
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)

    data = response.data[0] if hasattr(response, 'data') and response.data else None
    url = get_field(data, "url") if data else None
    b64_json = get_field(data, "b64_json") if data else None
    
    logger.debug("OpenAI response fields: url=%s b64_json=%s", bool(url), bool(b64_json))
    
    if url:
        image_url = url
        logger.debug("Downloading generated image from %s", image_url)
        img_data = requests.get(image_url).content
    elif b64_json:
        logger.debug("Decoding base64 image data from OpenAI response")
        img_data = base64.b64decode(b64_json)
    else:
        logger.debug("Full response from OpenAI API:\n%s", response)
        raise ValueError("No valid image data found in response. See debug output above.")

    with open(out_path, 'wb') as handler:
        handler.write(img_data)
    logger.debug("Wrote %d bytes to %s", len(img_data), out_path)
    return out_path


def generate_image(prompt, out_path, model="gpt-image-1.5", size="1024x1024", quality="medium", reference_images: list[str] | None = None):
    """Route to Google Imagen or OpenAI based on the requested model."""
    if model.startswith("imagen-"):
        return generate_image_google(prompt, out_path, model, quality=quality)
    else:
        return generate_image_openai(prompt, out_path, model, size=size, quality=quality, reference_images=reference_images)


def convert_png_to_webp(
    png_path: Path,
    webp_path: Path | None = None,
    *,
    max_dimension: int | None = None,
    lossless: bool = True,
    quality: int | None = None,
) -> Path:
    target_path = webp_path or png_path.with_suffix(".webp")
    logger.debug(
        "Converting PNG to WebP: source=%s target=%s max_dimension=%s lossless=%s quality=%s",
        png_path, target_path, max_dimension, lossless, quality,
    )
    with Image.open(png_path) as img:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        else:
            img = img.copy()

        if max_dimension is not None:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        save_kwargs = {"format": "WEBP"}
        if lossless:
            save_kwargs["lossless"] = True
        else:
            save_kwargs["lossless"] = False
            save_kwargs["method"] = 6
            if quality is not None:
                save_kwargs["quality"] = quality

        target_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(target_path, **save_kwargs)
    return target_path


def update_images_frontmatter_with_fmu(index_path: Path, image_name: str = "illustration.webp") -> bool:
    """Update the images frontmatter field via the 'fmu' external command."""
    command = [
        "fmu",
        "update",
        str(index_path),
        "--name",
        "images",
        "--compute",
        f"=flat_list({image_name})",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        if result.returncode == 0:
            return True
        logger.warning("fmu command failed with return code %d. Stderr: %s", result.returncode, result.stderr)
    except FileNotFoundError:
        logger.debug("fmu command not found on PATH. Standard YAML parsing will be used.")
    except Exception as e:
        logger.warning("Error running fmu: %s", e)
        
    return False


def update_index_frontmatter_images(index_path: Path, image_name: str = THUMBNAIL_WEBP_FILENAME) -> Path | None:
    """Update standard frontmatter images block in index.md using robust inline parsing."""
    if not index_path.exists():
        return None

    # First attempt updating using 'fmu' command if possible
    if update_images_frontmatter_with_fmu(index_path, image_name):
        logger.debug("Successfully updated frontmatter via fmu.")
        # Re-read file to return updated path
        return index_path

    try:
        text = index_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to read %s: %s", index_path, e)
        return None

    lines = text.splitlines()
    logger.debug("Updating frontmatter images in %s to include %s", index_path, image_name)

    if not lines or lines[0].strip() != "---":
        logger.warning("Skipping frontmatter update for %s: missing YAML frontmatter", index_path)
        return None

    try:
        frontmatter_end = lines.index("---", 1)
    except ValueError:
        logger.warning("Skipping frontmatter update for %s: unterminated YAML frontmatter", index_path)
        return None

    frontmatter_lines = lines[1:frontmatter_end]
    thumbnail_entry = f"- {image_name}"

    images_index = next((i for i, line in enumerate(frontmatter_lines) if line.strip() == "images:"), None)
    if images_index is None:
        insert_after = len(frontmatter_lines)
        for key in ("image:", "summary:", "url:"):
            key_index = next((i for i, line in enumerate(frontmatter_lines) if line.strip().startswith(key)), None)
            if key_index is not None:
                insert_after = key_index + 1
                break
        frontmatter_lines[insert_after:insert_after] = ["images:", thumbnail_entry]
    else:
        block_end = images_index + 1
        while block_end < len(frontmatter_lines) and frontmatter_lines[block_end].lstrip().startswith("-"):
            if frontmatter_lines[block_end].strip() == thumbnail_entry:
                # Value already exists, nothing to update
                return None
            block_end += 1
        frontmatter_lines.insert(block_end, thumbnail_entry)

    updated_text = "\n".join([lines[0], *frontmatter_lines, lines[frontmatter_end], *lines[frontmatter_end + 1:]])
    if text.endswith("\n"):
        updated_text += "\n"

    try:
        index_path.write_text(updated_text, encoding="utf-8")
        return index_path
    except Exception as e:
        logger.warning("Failed to write updated frontmatter to %s: %s", index_path, e)
        return None


def update_figure_shortcodes_in_index(index_path: Path) -> bool:
    """Replace any standard markdown figure shortcodes referencing .png with .webp."""
    if not index_path.exists():
        return False
        
    try:
        content = index_path.read_text(encoding="utf-8")
        if '{{< figure src="illustration.png"' in content:
            updated_content = content.replace('{{< figure src="illustration.png"', '{{< figure src="illustration.webp"')
            index_path.write_text(updated_content, encoding="utf-8")
            logger.info("Updated figure shortcode references in: %s", index_path)
            return True
    except Exception as e:
        logger.warning("Failed to update figure shortcodes in %s: %s", index_path, e)
        
    return False


def generate_image_from_prompt(
    prompt_path: Path, 
    out_path: Path, 
    model="dall-e-3", 
    quality="medium", 
    orientation="square", 
    reference_images: list[str] | None = None, 
    size: str | None = None
) -> Path:
    """Generate image based on prompt read from the filesystem, resolving size automatically."""
    try:
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.error("Failed to read prompt file %s: %s", prompt_path, e)
        sys.exit(1)
        
    logger.debug("Loaded prompt file %s (%d characters)", prompt_path, len(prompt))
    
    # Try to parse the size from the prompt file's name if not specified
    if not size:
        # Extract trailing suffix matching -<width>x<height>
        size_match = re.search(r'-(\d+)x(\d+)(?:\.txt)?$', prompt_path.name)
        if size_match:
            size = f"{size_match.group(1)}x{size_match.group(2)}"
            logger.debug("Parsed size %s from prompt filename %s", size, prompt_path.name)

    if not size:
        try:
            size = _resolve_size_for_orientation(model, orientation)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)
            
    print(f"Generating image for: {out_path} using model: {model}, quality: {quality}, orientation: {orientation}, size: {size}")
    
    # Prepend master prompt if present in the folder
    master_text = load_master_prompt(prompt_path.parent)
    prompt = combine_master_prompt(master_text, prompt)
    
    result_path = generate_image(
        prompt, 
        str(out_path), 
        model=model, 
        size=size, 
        quality=quality, 
        reference_images=reference_images
    )
    return Path(result_path)


def process_story_folder(
    source: str,
    model="dall-e-3",
    quality="medium",
    orientation="square",
    reference_images: list[str] | None = None,
    output_prefix: str | None = None,
    size: str | None = None,
    skip_update=False,
    force=False,
    file_pattern=None,
    basename=None,
):
    """Unified handler that can process entire story folders or individual files with optional filters."""
    source_path = Path(source)
    if not source_path.exists():
        print(f"Error: Path not found: {source_path}")
        return

    # Determine prompt files
    prompt_files = []
    
    if source_path.is_file():
        prompt_files = [source_path]
    else:
        # Source is a directory
        if basename:
            candidate = source_path / f"{basename}-prompt.txt"
            if candidate.exists():
                prompt_files = [candidate]
        elif file_pattern:
            import fnmatch
            try:
                files = os.listdir(source_path)
                prompt_files = [source_path / f for f in files if fnmatch.fnmatch(f, file_pattern)]
            except Exception as e:
                logger.error("Failed to list directory %s: %s", source_path, e)
                return
        else:
            # Default lookup: illustration-prompt*.txt
            prompt_files = sorted(source_path.glob("illustration-prompt*.txt"))
            # Fallback to legacy file name if none found
            if not prompt_files:
                legacy = source_path / "illustration-prompt.txt"
                if legacy.exists():
                    prompt_files = [legacy]

    if not prompt_files:
        print(f"No prompt files found in: {source}")
        return

    for prompt_file in prompt_files:
        # Check master prompt and skip it if it was matched accidentally
        if prompt_file.name == "illustration-master-prompt.txt":
            logger.debug("Skipping master prompt file: %s", prompt_file)
            continue
            
        # Determine output PNG base name
        if source_path.is_file():
            # Source is file: out base name is prompt name minus '-prompt'
            stem = prompt_file.stem
            out_base = stem.replace("-prompt", "", 1)
            png_filename = f"{out_base}.png"
            if output_prefix:
                png_filename = f"{output_prefix}-{png_filename}"
            png_path = prompt_file.with_name(png_filename)
        else:
            # Source is directory: default output filename is featured.png or base derived from prompt
            stem = prompt_file.stem
            out_base = stem.replace("-prompt", "", 1)
            # Default to "featured.png" for standard single-illustration case, or derivative
            if out_base == "illustration":
                png_filename = "featured.png"
            else:
                png_filename = f"{out_base}.png"
                
            if output_prefix:
                png_filename = f"{output_prefix}-{png_filename}"
            png_path = source_path / png_filename

        # Derive WebP and final target paths
        featured_webp_name = FEATURED_WEBP_FILENAME
        thumbnail_webp_name = THUMBNAIL_WEBP_FILENAME
        if output_prefix:
            featured_webp_name = f"{output_prefix}-{FEATURED_WEBP_FILENAME}"
            thumbnail_webp_name = f"{output_prefix}-{THUMBNAIL_WEBP_FILENAME}"

        featured_webp_path = png_path.with_name(featured_webp_name)
        thumbnail_webp_path = png_path.with_name(thumbnail_webp_name)

        # Skip regeneration if not forced and target outputs already exist
        if not force and (featured_webp_path.exists() or png_path.exists()):
            print(f"Skipping {png_path.name} (already exists)")
            continue

        # Generate PNG
        generated_png = generate_image_from_prompt(
            prompt_file, 
            png_path, 
            model=model, 
            quality=quality, 
            orientation=orientation, 
            reference_images=reference_images, 
            size=size
        )

        # Convert to featured/optimized WebPs
        convert_png_to_webp(generated_png, featured_webp_path)
        convert_png_to_webp(
            generated_png,
            thumbnail_webp_path,
            max_dimension=THUMBNAIL_MAX_DIMENSION,
            lossless=False,
            quality=THUMBNAIL_WEBP_QUALITY,
        )

        print(f"Saved: {generated_png}")
        print(f"Saved: {featured_webp_path}")
        print(f"Saved: {thumbnail_webp_path}")

        # Update Jekyll/Hugo post if index.md exists
        if not skip_update:
            article_dir = source_path if source_path.is_dir() else source_path.parent
            index_path = article_dir / "index.md"
            if index_path.exists():
                updated_index = update_index_frontmatter_images(index_path, image_name=thumbnail_webp_name)
                if updated_index:
                    print(f"Updated: {updated_index}")
                # Also replace figure references
                update_figure_shortcodes_in_index(index_path)
