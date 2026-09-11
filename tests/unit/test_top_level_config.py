"""Unit tests for the top-level vantagecv.config.Config class.

This is a separate, simpler YAML wrapper from research_v2/config.py's
ResearchConfig -- still exported as vantagecv.Config via __init__.py.
"""

import pytest
import yaml

from vantagecv.config import Config


class TestConfigLoading:
    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Config(str(tmp_path / "does_not_exist.yaml"))

    def test_loads_real_yaml_file(self, tmp_path):
        path = tmp_path / "cfg.yaml"
        path.write_text(yaml.dump({"a": 1, "b": {"c": 2}}), encoding="utf-8")
        cfg = Config(str(path))
        assert cfg.data == {"a": 1, "b": {"c": 2}}


class TestConfigGetDotPath:
    def _config(self, tmp_path, data):
        path = tmp_path / "cfg.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")
        return Config(str(path))

    def test_top_level_key(self, tmp_path):
        cfg = self._config(tmp_path, {"a": 1})
        assert cfg.get("a") == 1

    def test_nested_dot_path(self, tmp_path):
        cfg = self._config(tmp_path, {"camera": {"resolution": [1920, 1080]}})
        assert cfg.get("camera.resolution") == [1920, 1080]

    def test_missing_key_returns_default(self, tmp_path):
        cfg = self._config(tmp_path, {"a": 1})
        assert cfg.get("nonexistent", "fallback") == "fallback"

    def test_missing_key_returns_none_by_default(self, tmp_path):
        cfg = self._config(tmp_path, {"a": 1})
        assert cfg.get("nonexistent") is None

    def test_partial_path_through_non_dict_returns_default(self, tmp_path):
        cfg = self._config(tmp_path, {"a": 1})
        assert cfg.get("a.b.c", "fallback") == "fallback"

    def test_explicit_null_value_indistinguishable_from_missing(self, tmp_path):
        """KNOWN LIMITATION: get() returns `default` both when a key is
        missing AND when its YAML value is explicitly null -- it cannot
        tell the two apart, since the `if value is None: return default`
        check fires either way."""
        cfg = self._config(tmp_path, {"explicit_null": None})
        assert cfg.get("explicit_null", "fallback") == "fallback"
        assert cfg.get("truly_missing", "fallback") == "fallback"


class TestConfigGetItem:
    def test_getitem_is_not_dot_path_aware(self, tmp_path):
        path = tmp_path / "cfg.yaml"
        path.write_text(yaml.dump({"camera.resolution": "literal-key"}), encoding="utf-8")
        cfg = Config(str(path))
        # The dotted string is a literal top-level key here (yaml.dump won't
        # nest it just because it contains a dot), confirming __getitem__
        # does a plain single-level lookup, not dot-path traversal.
        assert cfg["camera.resolution"] == "literal-key"

    def test_getitem_raises_key_error_for_dotted_path_into_nested_dict(self, tmp_path):
        path = tmp_path / "cfg.yaml"
        path.write_text(yaml.dump({"camera": {"resolution": [1920, 1080]}}), encoding="utf-8")
        cfg = Config(str(path))
        with pytest.raises(KeyError):
            cfg["camera.resolution"]  # not dot-path aware, unlike .get()

    def test_getitem_top_level_key_works(self, tmp_path):
        path = tmp_path / "cfg.yaml"
        path.write_text(yaml.dump({"camera": {"resolution": [1920, 1080]}}), encoding="utf-8")
        cfg = Config(str(path))
        assert cfg["camera"] == {"resolution": [1920, 1080]}


class TestConfigExportedFromPackage:
    def test_vantagecv_exports_config_class(self):
        import vantagecv

        assert vantagecv.Config is Config
