"""
Unit test for configuration and limits loading.
"""
import sys
import unittest
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import Settings
from app.core.limits import IngestionLimits


class TestConfigAndLimits(unittest.TestCase):
    def test_default_limits(self):
        limits = IngestionLimits()
        self.assertEqual(limits.max_zip_mb, 100)
        self.assertEqual(limits.max_files, 3000)
        self.assertEqual(limits.max_file_kb, 1000)
        self.assertEqual(limits.retention_days, 7)
        self.assertEqual(limits.max_zip_bytes, 100 * 1024 * 1024)
        self.assertEqual(limits.max_file_bytes, 1000 * 1024)

    def test_limit_validation(self):
        limits = IngestionLimits()
        self.assertTrue(limits.validate_file_size(500 * 1024))
        self.assertFalse(limits.validate_file_size(1200 * 1024))
        self.assertTrue(limits.validate_archive_size(50 * 1024 * 1024))
        self.assertFalse(limits.validate_archive_size(110 * 1024 * 1024))
        self.assertTrue(limits.validate_file_count(2999))
        self.assertFalse(limits.validate_file_count(3001))

    def test_settings_safe_defaults(self):
        settings = Settings()
        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 8000)
        self.assertIn("http://localhost:3000", settings.cors_origins)

    def test_llm_validation_placeholder_detection(self):
        settings = Settings(llm_provider="google_genai", gemini_api_key="your_gemini_api_key_here")
        valid, msg = settings.validate_llm_configuration()
        self.assertFalse(valid)
        self.assertIn("not configured or contains placeholder", msg)

        settings_mock = Settings(llm_provider="mock")
        valid, msg = settings_mock.validate_llm_configuration()
        self.assertTrue(valid)


if __name__ == "__main__":
    unittest.main()
