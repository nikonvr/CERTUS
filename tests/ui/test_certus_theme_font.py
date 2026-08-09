import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from certus.core.certus_core import load_font_config, save_font_config
from certus.ui.certus_theme import CertusTheme
from CERTUS_HUB import CertusHub


@pytest.fixture
def mock_app(qapp):
    """Ensure QApplication exists."""
    return qapp


def test_save_load_font_config(tmp_path, monkeypatch):
    """Test that the font configuration is correctly saved and loaded without regressions."""
    
    # Mock get_resource_path to point to a temporary test file
    test_json = tmp_path / "certus_theme.json"
    
    # Needs to match how get_resource_path is used in certus_core
    from certus.core import certus_core
    
    original_get_path = certus_core.get_resource_path
    
    def mock_get_resource_path(filename):
        if filename == "certus_theme.json":
            return str(test_json)
        return original_get_path(filename)
        
    monkeypatch.setattr(certus_core, "get_resource_path", mock_get_resource_path)
    
    # Save a specific font
    save_font_config("Gemini")
    
    # Reload and check
    loaded_font = load_font_config()
    assert loaded_font == "Gemini", f"Expected 'Gemini', got '{loaded_font}'"

    # Save another font
    save_font_config("iOS (San Francisco)")
    assert load_font_config() == "iOS (San Francisco)"


def test_theme_apply_font_family(mock_app, monkeypatch):
    """Test that CertusTheme.apply_to_app correctly resolves font choices."""
    
    # Test fallback default
    monkeypatch.setattr("certus.core.certus_core.load_font_config", lambda: "Default")
    CertusTheme.apply_to_app(mock_app, dark_mode=False)
    # The font family string should contain Segoe UI or Inter
    assert "Segoe UI" in CertusTheme.FONT_FAMILY or "Inter" in CertusTheme.FONT_FAMILY
    
    # Test Gemini choice
    monkeypatch.setattr("certus.core.certus_core.load_font_config", lambda: "Gemini")
    CertusTheme.apply_to_app(mock_app, dark_mode=False)
    assert "Google Sans" in CertusTheme.FONT_FAMILY

    # Test iOS choice
    monkeypatch.setattr("certus.core.certus_core.load_font_config", lambda: "iOS (San Francisco)")
    CertusTheme.apply_to_app(mock_app, dark_mode=False)
    assert ".AppleSystemUIFont" in CertusTheme.FONT_FAMILY


def test_certus_hub_font_combobox(mock_app, monkeypatch):
    """Test the CertusHub UI integration for the font combobox."""
    
    import CERTUS_HUB
    
    # Start with a known state
    monkeypatch.setattr(CERTUS_HUB, "load_font_config", lambda: "Roboto")
    
    # Track if save_font_config is called
    saved_fonts = []
    
    original_save = CERTUS_HUB.save_font_config
    
    def mock_save_font(font_name):
        saved_fonts.append(font_name)
        original_save(font_name)
        
    monkeypatch.setattr(CERTUS_HUB, "save_font_config", mock_save_font)
    
    hub = CertusHub()
    
    # Verify the combobox initializes correctly
    assert hub.cmb_font.currentText() == "Roboto"
    
    # Change the combobox selection
    hub.cmb_font.setCurrentText("Open Sans")
    
    # Verify it saved
    assert "Open Sans" in saved_fonts
    
    #Verify theme was applied with Open Sans
    assert "Open Sans" in CertusTheme.FONT_FAMILY
