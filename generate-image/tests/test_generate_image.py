import os
from pathlib import Path
from unittest import mock

try:
    import pytest
except ImportError:
    class MockPytest:
        class RaisesContext:
            def __init__(self, expected_exception):
                self.expected_exception = expected_exception
                self.value = None
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    raise AssertionError(f"Did not raise {self.expected_exception}")
                if issubclass(exc_type, self.expected_exception):
                    self.value = exc_val
                    return True
                return False
        def raises(self, expected_exception):
            return self.RaisesContext(expected_exception)
    pytest = MockPytest()

from tlnw_generate_image.core import (
    get_default_quality,
    normalize_quality_for_model,
    _resolve_size_for_orientation,
    combine_master_prompt,
    update_index_frontmatter_images,
    update_figure_shortcodes_in_index,
    load_master_prompt,
)

def test_get_default_quality():
    assert get_default_quality("imagen-4") == "standard"
    assert get_default_quality("gpt-image-1.5") == "medium"
    assert get_default_quality("dall-e-3") == "standard"
    assert get_default_quality("unknown-model") == "standard"

def test_normalize_quality_for_model():
    # gpt-image mapping
    assert normalize_quality_for_model("gpt-image-1.5", "standard") == "medium"
    assert normalize_quality_for_model("gpt-image-1.5", "hd") == "high"
    assert normalize_quality_for_model("gpt-image-1.5", "low") == "low"
    
    # dall-e-3 mapping
    assert normalize_quality_for_model("dall-e-3", "hd") == "hd"
    assert normalize_quality_for_model("dall-e-3", "high") == "hd"
    assert normalize_quality_for_model("dall-e-3", "medium") == "standard"
    
    # imagen mapping
    assert normalize_quality_for_model("imagen-4.0", "medium") == "standard"
    assert normalize_quality_for_model("imagen-4.0", "hd") == "high"

def test_resolve_size_for_orientation():
    assert _resolve_size_for_orientation("gpt-image-1.5", "square") == "1024x1024"
    assert _resolve_size_for_orientation("dall-e-3", "landscape") == "1792x1024"
    assert _resolve_size_for_orientation("dall-e-3", "portrait") == "1024x1792"
    assert _resolve_size_for_orientation("gpt-image-1.5", "landscape") == "1536x1024"
    assert _resolve_size_for_orientation("gpt-image-1.5", "portrait") == "1024x1536"
    
    with pytest.raises(ValueError):
        _resolve_size_for_orientation("dall-e-2", "landscape")

def test_combine_master_prompt():
    assert combine_master_prompt("", "Specific scene") == "Specific scene"
    assert combine_master_prompt("Master Style Note", "Scene details") == "Master Style Note\n\nScene details"

def test_load_master_prompt(tmp_path=None):
    if tmp_path is None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            _test_load_master_prompt_logic(Path(tmpdir))
    else:
        _test_load_master_prompt_logic(tmp_path)

def _test_load_master_prompt_logic(tmp_path):
    # Missing master prompt
    assert load_master_prompt(tmp_path) == ""
    
    # Existing master prompt
    master_file = tmp_path / "illustration-master-prompt.txt"
    master_file.write_text("Paint in impressionism style.", encoding="utf-8")
    assert load_master_prompt(tmp_path) == "Paint in impressionism style."

def test_update_index_frontmatter_images(tmp_path=None):
    with mock.patch('tlnw_generate_image.core.update_images_frontmatter_with_fmu', return_value=False):
        if tmp_path is None:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                _test_update_index_frontmatter_images_logic(Path(tmpdir))
        else:
            _test_update_index_frontmatter_images_logic(tmp_path)

def _test_update_index_frontmatter_images_logic(tmp_path):
    index_md = tmp_path / "index.md"
    
    # Standard Jekyll/Hugo markdown frontmatter
    initial_content = """---
title: My Story
summary: A nice summary
image: some-image.jpg
---
This is some content.
"""
    index_md.write_text(initial_content, encoding="utf-8")
    
    # Update and check
    res = update_index_frontmatter_images(index_md, "thumbnail.webp")
    assert res is not None
    assert res.exists()
    
    updated_content = res.read_text(encoding="utf-8")
    assert "images:" in updated_content
    assert "- thumbnail.webp" in updated_content
    
    # Re-updating with the same image name should return None (no change) or keep it idempotent
    res2 = update_index_frontmatter_images(index_md, "thumbnail.webp")
    assert res2 is None  # Matches the core logic return None when nothing needs update

def test_update_figure_shortcodes_in_index(tmp_path=None):
    if tmp_path is None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            _test_update_figure_shortcodes_in_index_logic(Path(tmpdir))
    else:
        _test_update_figure_shortcodes_in_index_logic(tmp_path)

def _test_update_figure_shortcodes_in_index_logic(tmp_path):
    index_md = tmp_path / "index.md"
    content = """---
title: Post
---
{{< figure src="illustration.png" title="Story" >}}
"""
    index_md.write_text(content, encoding="utf-8")
    
    updated = update_figure_shortcodes_in_index(index_md)
    assert updated is True
    
    new_content = index_md.read_text(encoding="utf-8")
    assert '{{< figure src="illustration.webp"' in new_content
