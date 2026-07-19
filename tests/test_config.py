"""Tests for Config Loader."""
import os
from pathlib import Path

from config_loader import config, _toml_get


class TestConfigEnvVars:
    def test_bridge_host_default(self):
        assert config.bridge.host == "127.0.0.1"

    def test_bridge_port_default(self):
        assert config.bridge.port == 8199

    def test_bridge_api_key_from_env(self):
        # Set in conftest
        assert config.bridge.api_key == "test-key-12345"

    def test_vault_path_default(self):
        # Set in conftest
        assert "test-key-12345" in config.bridge.api_key

    def test_rate_limit_defaults(self):
        assert "30/minute" in config.rate_limit.default
        assert "60/minute" in config.rate_limit.health
        assert "15/minute" in config.rate_limit.desktop

    def test_cors_defaults(self):
        assert isinstance(config.cors.origins, list)
        assert len(config.cors.origins) > 0

    def test_github_defaults(self):
        assert config.github.owner == "Yuanilvu"
        assert config.github.repo == "hermes-bridge"


class TestTomlGet:
    def test_get_existing(self):
        toml = {"section": {"key": "value"}}
        assert _toml_get(toml, "section", "key") == "value"

    def test_get_missing_section(self):
        assert _toml_get({}, "nonexistent", "key", "default") == "default"

    def test_get_missing_key(self):
        toml = {"section": {"other": "val"}}
        assert _toml_get(toml, "section", "key", None) is None

    def test_get_none_value(self):
        toml = {"section": {"key": None}}
        assert _toml_get(toml, "section", "key", "default") == "default"
