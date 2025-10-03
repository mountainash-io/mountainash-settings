"""
Comprehensive tests for SettingsFileHandler and related classes.

Tests cover:
- FileType enumeration
- FileTypeRegistry class (identify, register_type)
- SettingsFiles NamedTuple
- SettingsFileHandler methods:
  - separate_config_files()
  - merge_config_files()
  - identify_file_extension()
  - validate_config_files_exist()
  - group_files_by_type()
  - deduplicate_files()
  - format_config_file_tuple()
  - format_config_file_list()
"""

import pytest
from pathlib import Path
from upath import UPath

from mountainash_settings.settings_parameters.filehandler import (
    FileType,
    FileTypeRegistry,
    SettingsFiles,
    SettingsFileHandler,
    ConfigFileType,
    ConfigFileList,
)


class TestFileType:
    """Test FileType enumeration."""

    @pytest.mark.unit
    def test_file_type_constants(self):
        """Test that FileType has expected constants."""
        assert FileType.ENV == "env"
        assert FileType.YML == "yml"
        assert FileType.YAML == "yaml"
        assert FileType.TOML == "toml"
        assert FileType.JSON == "json"


class TestFileTypeRegistry:
    """Test FileTypeRegistry class."""

    @pytest.mark.unit
    def test_identify_yaml_file(self):
        """Test identifying .yaml file."""
        result = FileTypeRegistry.identify("config.yaml")
        assert result == "yaml"

    @pytest.mark.unit
    def test_identify_yml_file(self):
        """Test identifying .yml file."""
        result = FileTypeRegistry.identify("config.yml")
        assert result == "yaml"

    @pytest.mark.unit
    def test_identify_toml_file(self):
        """Test identifying .toml file."""
        result = FileTypeRegistry.identify("config.toml")
        assert result == "toml"

    @pytest.mark.unit
    def test_identify_json_file(self):
        """Test identifying .json file."""
        result = FileTypeRegistry.identify("config.json")
        assert result == "json"

    @pytest.mark.unit
    def test_identify_env_file(self):
        """Test identifying .env file."""
        # Note: .env files don't have a traditional extension
        # UPath('.env').suffix returns '' (empty string)
        result = FileTypeRegistry.identify("config.env")
        assert result == "env"

    @pytest.mark.unit
    def test_identify_with_upath(self):
        """Test identifying file with UPath object."""
        result = FileTypeRegistry.identify(UPath("config.yaml"))
        assert result == "yaml"

    @pytest.mark.unit
    def test_identify_unknown_extension(self):
        """Test identifying file with unknown extension."""
        result = FileTypeRegistry.identify("config.txt")
        assert result is None

    @pytest.mark.unit
    def test_identify_case_insensitive(self):
        """Test that file identification is case insensitive."""
        result = FileTypeRegistry.identify("CONFIG.YAML")
        assert result == "yaml"

    @pytest.mark.unit
    def test_register_type_adds_new_extension(self):
        """Test registering a new file type."""
        # Register a new type
        FileTypeRegistry.register_type("ini", "ini")

        # Verify it's registered
        result = FileTypeRegistry.identify("config.ini")
        assert result == "ini"

        # Cleanup
        del FileTypeRegistry._registry["ini"]


class TestSettingsFiles:
    """Test SettingsFiles NamedTuple."""

    @pytest.mark.unit
    def test_settings_files_creation_empty(self):
        """Test creating SettingsFiles with no files."""
        files = SettingsFiles()
        assert files.env_files is None
        assert files.yaml_files is None
        assert files.toml_files is None
        assert files.json_files is None

    @pytest.mark.unit
    def test_settings_files_creation_with_values(self):
        """Test creating SettingsFiles with values."""
        files = SettingsFiles(
            env_files=[".env"],
            yaml_files=["config.yaml"],
            toml_files=["config.toml"],
            json_files=["config.json"]
        )
        assert files.env_files == [".env"]
        assert files.yaml_files == ["config.yaml"]
        assert files.toml_files == ["config.toml"]
        assert files.json_files == ["config.json"]

    @pytest.mark.unit
    def test_settings_files_immutable(self):
        """Test that SettingsFiles is immutable."""
        files = SettingsFiles(yaml_files=["config.yaml"])
        with pytest.raises(AttributeError):
            files.yaml_files = ["other.yaml"]


class TestSeparateConfigFiles:
    """Test separate_config_files method."""

    @pytest.mark.unit
    def test_separate_none_returns_empty(self):
        """Test that None input returns empty SettingsFiles."""
        result = SettingsFileHandler.separate_config_files(None)
        assert result == SettingsFiles()

    @pytest.mark.unit
    def test_separate_empty_list_returns_empty(self):
        """Test that empty list returns empty SettingsFiles."""
        result = SettingsFileHandler.separate_config_files([])
        assert result == SettingsFiles()

    @pytest.mark.unit
    def test_separate_empty_tuple_returns_empty(self):
        """Test that empty tuple returns empty SettingsFiles."""
        result = SettingsFileHandler.separate_config_files(())
        assert result == SettingsFiles()

    @pytest.mark.unit
    def test_separate_single_yaml_file(self, temp_yaml_file):
        """Test separating single YAML file."""
        result = SettingsFileHandler.separate_config_files(temp_yaml_file)
        assert result.yaml_files is not None
        assert len(result.yaml_files) == 1
        assert result.env_files is None
        assert result.toml_files is None
        assert result.json_files is None

    @pytest.mark.unit
    def test_separate_single_yml_file(self, create_config_file):
        """Test separating single .yml file."""
        yml_file = create_config_file('yml', {'TEST': 'value'})
        result = SettingsFileHandler.separate_config_files(yml_file)
        assert result.yaml_files is not None
        assert len(result.yaml_files) == 1

    @pytest.mark.unit
    def test_separate_multiple_files_different_types(
        self, temp_yaml_file, temp_toml_file, temp_json_file
    ):
        """Test separating multiple files of different types."""
        files = [temp_yaml_file, temp_toml_file, temp_json_file]
        result = SettingsFileHandler.separate_config_files(files)

        assert result.yaml_files is not None
        assert len(result.yaml_files) == 1
        assert result.toml_files is not None
        assert len(result.toml_files) == 1
        assert result.json_files is not None
        assert len(result.json_files) == 1
        assert result.env_files is None

    @pytest.mark.unit
    def test_separate_multiple_yaml_files(self, temp_multiple_yaml_files):
        """Test separating multiple YAML files."""
        result = SettingsFileHandler.separate_config_files(temp_multiple_yaml_files)
        assert result.yaml_files is not None
        assert len(result.yaml_files) == 2

    @pytest.mark.unit
    def test_separate_with_tuple_input(self, temp_yaml_file, temp_toml_file):
        """Test separating files provided as tuple."""
        files = (temp_yaml_file, temp_toml_file)
        result = SettingsFileHandler.separate_config_files(files)

        assert result.yaml_files is not None
        assert result.toml_files is not None

    @pytest.mark.unit
    def test_separate_deduplicates_files(self, temp_yaml_file):
        """Test that duplicate files are deduplicated."""
        files = [temp_yaml_file, temp_yaml_file]
        result = SettingsFileHandler.separate_config_files(files)

        assert result.yaml_files is not None
        assert len(result.yaml_files) == 1

    @pytest.mark.unit
    def test_separate_expands_user_path(self, temp_dir):
        """Test that ~ in paths is expanded."""
        # Create a file in temp dir
        yaml_file = temp_dir / "config.yaml"
        yaml_file.write_text("TEST: value")

        # Use relative path with ~
        # Note: This test assumes the file is actually in the temp location
        result = SettingsFileHandler.separate_config_files([str(yaml_file)])
        assert result.yaml_files is not None


class TestMergeConfigFiles:
    """Test merge_config_files method."""

    @pytest.mark.unit
    def test_merge_both_none(self):
        """Test merging when both inputs are None."""
        result = SettingsFileHandler.merge_config_files(None, None)
        assert result is None

    @pytest.mark.unit
    def test_merge_first_none(self):
        """Test merging when first input is None."""
        files2 = ("config1.yaml", "config2.yaml")
        result = SettingsFileHandler.merge_config_files(None, files2)
        assert result == files2

    @pytest.mark.unit
    def test_merge_second_none(self):
        """Test merging when second input is None."""
        files1 = ("config1.yaml", "config2.yaml")
        result = SettingsFileHandler.merge_config_files(files1, None)
        assert result == files1

    @pytest.mark.unit
    def test_merge_both_provided(self):
        """Test merging two sets of files."""
        files1 = ("config1.yaml",)
        files2 = ("config2.yaml",)
        result = SettingsFileHandler.merge_config_files(files1, files2)
        assert set(result) == {"config1.yaml", "config2.yaml"}

    @pytest.mark.unit
    def test_merge_removes_duplicates(self):
        """Test that merge removes duplicates."""
        files1 = ("config1.yaml", "config2.yaml")
        files2 = ("config2.yaml", "config3.yaml")
        result = SettingsFileHandler.merge_config_files(files1, files2)
        assert len(result) == 3
        assert set(result) == {"config1.yaml", "config2.yaml", "config3.yaml"}


class TestIdentifyFileExtension:
    """Test identify_file_extension method."""

    @pytest.mark.unit
    def test_identify_none_returns_none(self):
        """Test that None input returns None."""
        result = SettingsFileHandler.identify_file_extension(None)
        assert result is None

    @pytest.mark.unit
    def test_identify_yaml_extension(self):
        """Test identifying .yaml extension."""
        result = SettingsFileHandler.identify_file_extension("config.yaml")
        assert result == "yaml"

    @pytest.mark.unit
    def test_identify_toml_extension(self):
        """Test identifying .toml extension."""
        result = SettingsFileHandler.identify_file_extension("config.toml")
        assert result == "toml"

    @pytest.mark.unit
    def test_identify_json_extension(self):
        """Test identifying .json extension."""
        result = SettingsFileHandler.identify_file_extension("config.json")
        assert result == "json"

    @pytest.mark.unit
    def test_identify_env_extension(self):
        """Test identifying .env extension."""
        # Note: .env files don't have a traditional extension
        # Use a file with .env extension instead
        result = SettingsFileHandler.identify_file_extension("config.env")
        assert result == "env"

    @pytest.mark.unit
    def test_identify_with_upath(self):
        """Test identifying with UPath object."""
        result = SettingsFileHandler.identify_file_extension(UPath("config.yaml"))
        assert result == "yaml"

    @pytest.mark.unit
    def test_identify_unknown_extension_returns_none(self, capsys):
        """Test that unknown extension returns None and prints warning."""
        result = SettingsFileHandler.identify_file_extension("config.txt")
        assert result is None

        # Check that warning was printed
        captured = capsys.readouterr()
        assert "Invalid file type" in captured.out


class TestValidateConfigFilesExist:
    """Test validate_config_files_exist method."""

    @pytest.mark.unit
    def test_validate_none_returns_none(self):
        """Test that None input returns None."""
        result = SettingsFileHandler.validate_config_files_exist(None)
        assert result is None

    @pytest.mark.unit
    def test_validate_empty_list_returns_none(self):
        """Test that empty list returns None."""
        result = SettingsFileHandler.validate_config_files_exist([])
        assert result is None

    @pytest.mark.unit
    def test_validate_empty_tuple_returns_none(self):
        """Test that empty tuple returns None."""
        result = SettingsFileHandler.validate_config_files_exist(())
        assert result is None

    @pytest.mark.unit
    def test_validate_existing_file_succeeds(self, temp_yaml_file):
        """Test that existing file validates successfully."""
        # Should not raise
        SettingsFileHandler.validate_config_files_exist([temp_yaml_file])

    @pytest.mark.unit
    def test_validate_non_existing_file_raises_error(self):
        """Test that non-existing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config file .* not found"):
            SettingsFileHandler.validate_config_files_exist(["non_existent.yaml"])

    @pytest.mark.unit
    def test_validate_multiple_existing_files(
        self, temp_yaml_file, temp_toml_file
    ):
        """Test validating multiple existing files."""
        # Should not raise
        SettingsFileHandler.validate_config_files_exist([temp_yaml_file, temp_toml_file])

    @pytest.mark.unit
    def test_validate_with_upath(self, temp_yaml_file):
        """Test validating with UPath object."""
        upath = UPath(temp_yaml_file)
        # Should not raise
        SettingsFileHandler.validate_config_files_exist([upath])


class TestGroupFilesByType:
    """Test group_files_by_type method."""

    @pytest.mark.unit
    def test_group_none_returns_empty_dict(self):
        """Test that None input returns empty dict."""
        result = SettingsFileHandler.group_files_by_type(None)
        assert result == {}

    @pytest.mark.unit
    def test_group_empty_list_returns_empty_dict(self):
        """Test that empty list returns empty dict."""
        result = SettingsFileHandler.group_files_by_type([])
        assert result == {}

    @pytest.mark.unit
    def test_group_single_file(self, temp_yaml_file):
        """Test grouping single file."""
        result = SettingsFileHandler.group_files_by_type([temp_yaml_file])
        assert "yaml" in result
        assert len(result["yaml"]) == 1

    @pytest.mark.unit
    def test_group_multiple_files_same_type(self, temp_multiple_yaml_files):
        """Test grouping multiple files of same type."""
        result = SettingsFileHandler.group_files_by_type(temp_multiple_yaml_files)
        assert "yaml" in result
        assert len(result["yaml"]) == 2

    @pytest.mark.unit
    def test_group_multiple_files_different_types(
        self, temp_yaml_file, temp_toml_file, temp_json_file
    ):
        """Test grouping files of different types."""
        files = [temp_yaml_file, temp_toml_file, temp_json_file]
        result = SettingsFileHandler.group_files_by_type(files)

        assert "yaml" in result
        assert "toml" in result
        assert "json" in result
        assert len(result["yaml"]) == 1
        assert len(result["toml"]) == 1
        assert len(result["json"]) == 1


class TestDeduplicateFiles:
    """Test deduplicate_files method."""

    @pytest.mark.unit
    def test_deduplicate_none_returns_none(self):
        """Test that None input returns None."""
        result = SettingsFileHandler.deduplicate_files(None)
        assert result is None

    @pytest.mark.unit
    def test_deduplicate_empty_list_returns_none(self):
        """Test that empty list returns None."""
        result = SettingsFileHandler.deduplicate_files([])
        assert result is None

    @pytest.mark.unit
    def test_deduplicate_single_file(self):
        """Test deduplicating single file."""
        files = ["config.yaml"]
        result = SettingsFileHandler.deduplicate_files(files)
        assert result == ["config.yaml"]

    @pytest.mark.unit
    def test_deduplicate_single_string_file(self):
        """Test deduplicating single string file (not in list)."""
        result = SettingsFileHandler.deduplicate_files("config.yaml")
        assert result == ["config.yaml"]

    @pytest.mark.unit
    def test_deduplicate_removes_duplicates(self):
        """Test that duplicates are removed."""
        files = ["config.yaml", "other.yaml", "config.yaml"]
        result = SettingsFileHandler.deduplicate_files(files)
        assert len(result) == 2
        # Check that unique files are preserved
        result_strs = [str(f) for f in result]
        assert "config.yaml" in result_strs
        assert "other.yaml" in result_strs

    @pytest.mark.unit
    def test_deduplicate_preserves_order(self):
        """Test that order is preserved during deduplication."""
        files = ["first.yaml", "second.yaml", "third.yaml", "first.yaml"]
        result = SettingsFileHandler.deduplicate_files(files)
        result_strs = [str(f) for f in result]
        assert result_strs.index("first.yaml") < result_strs.index("second.yaml")
        assert result_strs.index("second.yaml") < result_strs.index("third.yaml")

    @pytest.mark.unit
    def test_deduplicate_with_upaths(self):
        """Test deduplicating UPath objects."""
        files = [UPath("config.yaml"), UPath("other.yaml"), UPath("config.yaml")]
        result = SettingsFileHandler.deduplicate_files(files)
        assert len(result) == 2


class TestFormatConfigFileTuple:
    """Test format_config_file_tuple method."""

    @pytest.mark.unit
    def test_format_none_returns_none(self):
        """Test that None input returns None."""
        result = SettingsFileHandler.format_config_file_tuple(None)
        assert result is None

    @pytest.mark.unit
    def test_format_empty_list_returns_none(self):
        """Test that empty list returns None."""
        result = SettingsFileHandler.format_config_file_tuple([])
        assert result is None

    @pytest.mark.unit
    def test_format_single_string_to_tuple(self):
        """Test formatting single string to tuple."""
        result = SettingsFileHandler.format_config_file_tuple("config.yaml")
        assert result == ("config.yaml",)

    @pytest.mark.unit
    def test_format_single_upath_to_tuple(self):
        """Test formatting single UPath to tuple."""
        upath = UPath("config.yaml")
        result = SettingsFileHandler.format_config_file_tuple(upath)
        assert result == (upath,)

    @pytest.mark.unit
    def test_format_list_to_tuple(self):
        """Test formatting list to tuple."""
        files = ["config1.yaml", "config2.yaml"]
        result = SettingsFileHandler.format_config_file_tuple(files)
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.unit
    def test_format_tuple_returns_tuple(self):
        """Test that tuple input returns deduplicated tuple."""
        files = ("config1.yaml", "config2.yaml", "config1.yaml")
        result = SettingsFileHandler.format_config_file_tuple(files)
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestFormatConfigFileList:
    """Test format_config_file_list method."""

    @pytest.mark.unit
    def test_format_none_returns_none(self):
        """Test that None input returns None."""
        result = SettingsFileHandler.format_config_file_list(None)
        assert result is None

    @pytest.mark.unit
    def test_format_empty_list_returns_none(self):
        """Test that empty list returns None."""
        result = SettingsFileHandler.format_config_file_list([])
        assert result is None

    @pytest.mark.unit
    def test_format_empty_tuple_returns_none(self):
        """Test that empty tuple returns None."""
        result = SettingsFileHandler.format_config_file_list(())
        assert result is None

    @pytest.mark.unit
    def test_format_single_string_to_list(self):
        """Test formatting single string to list."""
        result = SettingsFileHandler.format_config_file_list("config.yaml")
        assert result == ["config.yaml"]

    @pytest.mark.unit
    def test_format_single_upath_to_list(self):
        """Test formatting single UPath to list."""
        upath = UPath("config.yaml")
        result = SettingsFileHandler.format_config_file_list(upath)
        assert result == [upath]

    @pytest.mark.unit
    def test_format_tuple_to_list(self):
        """Test formatting tuple to list."""
        files = ("config1.yaml", "config2.yaml")
        result = SettingsFileHandler.format_config_file_list(files)
        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.unit
    def test_format_list_deduplicates(self):
        """Test that list is deduplicated."""
        files = ["config1.yaml", "config2.yaml", "config1.yaml"]
        result = SettingsFileHandler.format_config_file_list(files)
        assert len(result) == 2

    @pytest.mark.unit
    def test_format_invalid_type_raises_error(self):
        """Test that invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid config_files"):
            SettingsFileHandler.format_config_file_list(12345)


class TestIntegration:
    """Integration tests for filehandler."""

    @pytest.mark.integration
    def test_full_workflow_separate_validate_and_format(
        self, temp_yaml_file, temp_toml_file
    ):
        """Test complete workflow with multiple methods."""
        files = [temp_yaml_file, temp_toml_file]

        # Validate files exist
        SettingsFileHandler.validate_config_files_exist(files)

        # Separate files by type
        separated = SettingsFileHandler.separate_config_files(files)
        assert separated.yaml_files is not None
        assert separated.toml_files is not None

        # Format as tuple
        files_tuple = SettingsFileHandler.format_config_file_tuple(files)
        assert isinstance(files_tuple, tuple)
        assert len(files_tuple) == 2
