"""Tests for configuration."""

import logging
from unittest.mock import patch

import pytest

from app.config import check_default_secret


class TestCheckDefaultSecret:
    def test_raises_on_default_secret(self):
        with patch("app.config.JWT_SECRET", "kg_log_secret_change_me_in_production"):
            with patch("app.config.DEV_MODE", False):
                with pytest.raises(RuntimeError, match="JWT_SECRET is set to a default value"):
                    check_default_secret()

    def test_warns_in_dev_mode(self, caplog):
        with patch("app.config.JWT_SECRET", "kg_log_secret_change_me_in_production"):
            with patch("app.config.DEV_MODE", True):
                with caplog.at_level(logging.WARNING, logger="klog"):
                    check_default_secret()
                assert "JWT_SECRET is set to a default value" in caplog.text

    def test_no_error_on_custom_secret(self):
        with patch("app.config.JWT_SECRET", "my_super_secure_random_secret"):
            with patch("app.config.DEV_MODE", False):
                check_default_secret()  # should not raise
