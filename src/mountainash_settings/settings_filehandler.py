from typing import Optional, Union, List, Tuple, Dict, NamedTuple
from upath import UPath
import os
from pathlib import Path

class ConfigFiles(NamedTuple):
    """Container for different types of configuration files"""
    env_files: Optional[List[Union[UPath, str]]] = None
    yaml_files: Optional[List[Union[UPath, str]]] = None
    toml_files: Optional[List[Union[UPath, str]]] = None

class FileType:
    """Enumeration of supported file types and their extensions"""
    ENV = "env"
    YAML = ("yaml", "yml")
    TOML = "toml"

class SettingsFileHandler:
    """Handles validation and separation of configuration files by type"""
    
    @staticmethod
    def separate_config_files(
        files: Optional[Union[UPath, str, List[Union[UPath, str]], Tuple[Union[UPath, str]]]]
    ) -> ConfigFiles:
        """
        Separates configuration files into their respective types.
        
        Args:
            files: Configuration files in various possible formats
            
        Returns:
            ConfigFiles: Named tuple containing separated file lists
            
        Raises:
            ValueError: If an invalid file type is encountered
        """
        if files is None:
            return ConfigFiles()
            
        # Convert to list if single file
        if isinstance(files, (str, UPath)):
            files = [files]
            
        # Convert tuple to list
        files = list(files)
        
        # Validate and group files
        file_groups = SettingsFileHandler._group_files_by_type(files)
        
        # Create ConfigFiles with deduplicated lists
        return ConfigFiles(
            env_files=SettingsFileHandler._deduplicate_files(file_groups.get(FileType.ENV, [])),
            yaml_files=SettingsFileHandler._deduplicate_files(
                file_groups.get(FileType.YAML[0], []) + file_groups.get(FileType.YAML[1], [])
            ),
            toml_files=SettingsFileHandler._deduplicate_files(file_groups.get(FileType.TOML, []))
        )

    @staticmethod
    def _validate_extension(file_path: Union[UPath, str]) -> str:
        """
        Validates file extension and returns the file type.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            str: Validated file extension
            
        Raises:
            ValueError: If file extension is invalid
        """
        # Convert to string if UPath
        path_str = str(file_path)
        
        # Get extension without leading dot
        ext = os.path.splitext(path_str)[1].lower().lstrip('.')
        
        # Validate extension
        if ext == FileType.ENV:
            return FileType.ENV
        elif ext in FileType.YAML:
            return ext
        elif ext == FileType.TOML:
            return FileType.TOML
        else:
            raise ValueError(
                f"Invalid file type: {ext}. Supported types are: "
                f".env, .yaml, .yml, .toml"
            )

    @staticmethod
    def _group_files_by_type(
        files: List[Union[UPath, str]]
    ) -> Dict[str, List[Union[UPath, str]]]:
        """
        Groups files by their extension type.
        
        Args:
            files: List of file paths
            
        Returns:
            Dict mapping file extensions to lists of files
        """
        grouped_files: Dict[str, List[Union[UPath, str]]] = {}
        
        for file in files:
            ext = SettingsFileHandler._validate_extension(file)
            if ext not in grouped_files:
                grouped_files[ext] = []
            grouped_files[ext].append(file)
            
        return grouped_files

    @staticmethod
    def _deduplicate_files(
        files: List[Union[UPath, str]]
    ) -> Optional[List[Union[UPath, str]]]:
        """
        Removes duplicate files while preserving order.
        
        Args:
            files: List of file paths
            
        Returns:
            Deduplicated list of files, or None if empty
        """
        if not files:
            return None
            
        # Use dict to preserve order while removing duplicates
        unique_files = list(dict.fromkeys(str(f) for f in files))
        
        # Convert back to original types
        return [
            UPath(f) if isinstance(files[0], UPath) else f 
            for f in unique_files
        ]