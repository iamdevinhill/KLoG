"""Tests for configuration."""

import logging
from unittest.mock import patch

from app.config import warn_default_secret


class TestWarnDefaultSecret:
    def test_warns_on_default_secret(self, caplog):
        with patch("app.config.JWT_SECRET", "kg_log_secret_change_me_in_production"):
            with caplog.at_level(logging.WARNING, logger="kg_log"):
                warn_default_secret()
            assert "JWT_SECRET is set to a default value" in caplog.text

    def test_no_warning_on_custom_secret(self, caplog):
        with patch("app.config.JWT_SECRET", "my_super_secure_random_secret"):
            with caplog.at_level(logging.WARNING, logger="kg_log"):
                warn_default_secret()
            assert "JWT_SECRET" not in caplog.text
