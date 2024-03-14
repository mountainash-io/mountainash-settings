import pytest
from typing import Any
from mountainash_settings.settings import SettingsUtils

##===========================
# Test formatting to and from hashable parameters

def test_format_kwargs_dict_none():
    # Arrange
    p_kwargs = None

    # Act
    result = SettingsUtils.format_kwargs_dict(p_kwargs)

    # Assert
    assert result is None

def test_format_kwargs_dict_dict():
    # Arrange
    p_kwargs = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABC"}    

    # Act
    result = SettingsUtils.format_kwargs_dict(p_kwargs)

    # Assert
    assert result == p_kwargs

def test_format_kwargs_dict_tuple():
    # Arrange

    p_kwargs = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABC"}    

    t_kwargs = (("ORGANISATION_TLA", "XYZ"),("PORTFOLIO_NAME", "ABC"))    
    # p_kwargs = (("ORGANISATION_TLA", "XYZ"),("PORTFOLIO_NAME", "ABC"))

    # Act
    result = SettingsUtils.format_kwargs_tuple(p_kwargs)

    # Assert
    # assert result == tuple({"ORGANISATION_TLA": "XYZ","PORTFOLIO_NAME": "ABC" })
    #assert result == (("ORGANISATION_TLA", "XYZ"),("PORTFOLIO_NAME", "ABC"))
    assert result == t_kwargs

def test_format_kwargs_tuple_dict():
    # Arrange
    # p_kwargs = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABC"}    
    p_kwargs = (("ORGANISATION_TLA", "XYZ"),("PORTFOLIO_NAME", "ABC"))

    d_kwargs = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABC"}

    # Act
    result = SettingsUtils.format_kwargs_dict(p_kwargs)

    # Assert
    assert result == d_kwargs

def test_format_kwargs_tuple_tuple():
    # Arrange

    # p_kwargs = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABC"}    
    p_kwargs = (("ORGANISATION_TLA", "XYZ"),("PORTFOLIO_NAME", "ABC"))

    d_kwargs = {"ORGANISATION_TLA": "XYZ", "PORTFOLIO_NAME": "ABC"}
    t_kwargs = SettingsUtils.format_kwargs_tuple(d_kwargs)

    # Act
    result = SettingsUtils.format_kwargs_tuple(p_kwargs)

    # Assert
    # assert result == (("ORGANISATION_TLA", "XYZ"),("PORTFOLIO_NAME", "ABC"))
    assert result == t_kwargs



def test_format_kwargs_dict_invalid_type():
    # Arrange
    p_kwargs = "invalid"

    # Act
    with pytest.raises(ValueError):
        result = SettingsUtils.format_kwargs_dict(p_kwargs=p_kwargs)

    # Assert
    # assert result is None
        

##===========================
# Test validation of kwargs helpers



# Test case for when both new_config_files and original_config_files are None
def test_resolve_config_files_both_none():

    assert SettingsUtils.resolve_config_files(new_config_files=None, original_config_files=None) is None

# Test case for when new_config_files is not None and original_config_files is None
def test_resolve_config_files_new_not_none():
    new_config_files: list[Any] = ["file1", "file2"]

    assert SettingsUtils.resolve_config_files(new_config_files=new_config_files) == new_config_files

# Test case for when new_config_files is None and original_config_files is not None
def test_resolve_config_files_original_not_none():
    original_config_files: list[Any] = ["file1", "file2"]

    assert SettingsUtils.resolve_config_files(original_config_files=original_config_files) == original_config_files

# Test case for when both new_config_files and original_config_files are not None
def test_resolve_config_files_both_not_none():

    new_config_files: list[Any] = ["file2", "file1"]
    original_config_files: list[Any] = ["file4", "file3", "file1"]
    expected_result: list[Any] = ["file1", "file2", "file3", "file4"]

    assert SettingsUtils.resolve_config_files(new_config_files=new_config_files,
                                        original_config_files=original_config_files) == expected_result
