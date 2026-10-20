import os
import unittest
from unittest.mock import patch

from app.core.config import cors_origins


class CorsConfigurationTests(unittest.TestCase):
    def test_local_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cors_origins(), ["http://localhost:5173"])

    def test_normalizes_and_deduplicates_explicit_origins(self):
        with patch.dict(os.environ, {"AGRIROUTE_CORS_ORIGINS": " https://farm.example/,https://farm.example, http://localhost:5173 "}):
            self.assertEqual(cors_origins(), ["https://farm.example", "http://localhost:5173"])

    def test_rejects_wildcard_and_non_origin_urls(self):
        for value in ("*", "https://farm.example/path", "ftp://farm.example", ""):
            with self.subTest(value=value), patch.dict(os.environ, {"AGRIROUTE_CORS_ORIGINS": value}):
                with self.assertRaises(RuntimeError):
                    cors_origins()


if __name__ == "__main__":
    unittest.main()
