
from typing import Optional, Union, List, Tuple, Dict, NamedTuple
from upath import UPath

class SettingsFiles(NamedTuple):
    """Container for different types of configuration files"""
    env_files: Optional[List[Union[UPath, str]]] = None
    yaml_files: Optional[List[Union[UPath, str]]] = None
    toml_files: Optional[List[Union[UPath, str]]] = None
    json_files: Optional[List[Union[UPath, str]]] = None

class FileType():
    """Enumeration of supported file types and their extensions"""
    ENV = "env"
    YML = "yml"
    YAML = "yaml"
    TOML = "toml"
    JSON = "json"

class SettingsFileHandler:
    """Handles validation and separation of configuration files by type"""
    
    @classmethod
    def separate_config_files(
        cls,
        config_files: Optional[Union[UPath, str, List[Union[UPath, str]], Tuple[Union[UPath, str]]]] = None
    ) -> SettingsFiles:
        """
        Separates configuration files into their respective types.
        
        Args:
            files: Configuration files in various possible formats
            
        Returns:
            ConfigFiles: Named tuple containing separated file lists
            
        Raises:
            ValueError: If an invalid file type is encountered
        """

        if config_files is None:
            return SettingsFiles()        

        if isinstance(config_files, (list, tuple)) and len(config_files) == 0:
            return SettingsFiles()        

        # Convert to list if single file
        if isinstance(config_files, (str, UPath)):
            config_files = [config_files]
            
        # Convert tuple to list
        config_files = list(config_files)
        
        # Validate and group files
        file_groups = cls.group_files_by_type(config_files)
        
        # Create ConfigFiles with deduplicated lists
        obj_config_files =  SettingsFiles(
            env_files=cls.deduplicate_files(file_groups.get(FileType.ENV, [])),
            yaml_files=cls.deduplicate_files(file_groups.get(FileType.YAML, []) + file_groups.get(FileType.YML, [])),
            toml_files=cls.deduplicate_files(file_groups.get(FileType.TOML,[])),
            json_files=cls.deduplicate_files(file_groups.get(FileType.JSON,[]))
        )


        return obj_config_files


    @staticmethod
    def merge_config_files(config_files1:   Optional[Tuple[Union[UPath, str], ...]] = None,
                            config_files2:  Optional[Tuple[Union[UPath, str], ...]] = None) -> Optional[Tuple[Union[UPath, str], ...]]:
        if config_files1 is None and config_files2 is None:
            return None
        merged = set(config_files1 or ()) | set(config_files2 or ())
        return tuple(sorted(merged))


    @staticmethod
    def identify_file_extension(file_path: Union[UPath, str]) -> Optional[str]:
        """
        Identify file extension and returns the file type.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            str: File extension
            
        """

        if file_path is None:
            return None

        # Convert to string if UPath
        path_str = UPath(file_path)

        ext = path_str.suffix.lower().lstrip('.')

        # Get extension without leading dot
        # ext = os.path.splitext(path_str)[1].lower().lstrip('.')
        
        # Validate extension
        if ext == FileType.ENV:
            return FileType.ENV
        elif ext  == FileType.YAML:
            return FileType.YAML
        elif ext  == FileType.YML:
            return FileType.YML
        elif ext == FileType.TOML:
            return FileType.TOML
        elif ext == FileType.JSON:
            return FileType.JSON
        else:
            print(
                f"Invalid file type: {ext} from file: '{file_path}''. Supported types are: "
                f".env, .yaml, .yml, .toml, .json"
            )

            return None    

    @staticmethod
    def validate_config_files_exist(
                                    config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]] = None
                                    ) -> None:
        """
        Validates that the configuration files exist.
        
        Args:
            config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
        """

        if config_files is None:
            return None        

        if isinstance(config_files, (list, tuple)) and len(config_files) == 0:
            return None        

        # if isinstance(config_files, (list, tuple)) and all(f is None for f in config_files):
        #     return None    

        config_files_list = list(sorted(set(config_files)))

        if config_files_list:

            for config_file_temp in config_files_list:
                

                if not isinstance(config_file_temp, UPath):
                    config_file_temp = UPath(config_file_temp)

                #Only works for local files
                if not config_file_temp.exists():
                # if not os.path.exists(path=config_file_temp):
                    raise FileNotFoundError(f"Config file {config_file_temp} not found.")
                    


    @classmethod
    def group_files_by_type(cls,
        config_files: List[Union[UPath, str]]
    ) -> Dict[str, List[Union[UPath, str]]]:
        """
        Groups files by their extension type.
        
        Args:
            config_files: List of file paths
            
        Returns:
            Dict mapping file extensions to lists of files
        """

        if config_files is None:
            return {}        

        if isinstance(config_files, (list, tuple)) and len(config_files) == 0:
            return {}        

        grouped_files: Dict[str, List[Union[UPath, str]]] = {}
        
        for file in config_files:

            ext = cls.identify_file_extension(file)

            if ext not in grouped_files:
                grouped_files[ext] = []

            grouped_files[ext].append(file)
            
        return grouped_files

    @staticmethod
    def deduplicate_files(
        config_files: List[Union[UPath, str]]
    ) -> Optional[UPath|str|List[Union[UPath, str]]]:
        """
        Removes duplicate files while preserving order.
        
        Args:
            config_files: List of file paths
            
        Returns:
            Deduplicated list of files, or None if empty
        """

        if config_files is None:
            return None        

        if isinstance(config_files, (list, tuple)) and len(config_files) == 0:
            return None        
      
        if isinstance(config_files, (list, tuple)) and len(config_files) == 1:
            return list(config_files)

        if isinstance(config_files, (str, UPath)):
            return [config_files]

        # Use dict to preserve order while removing duplicates
        unique_files = list(dict.fromkeys(str(f) for f in config_files))
        
        # Convert to UPath
        return [
            UPath(f) #if isinstance(config_files[0], UPath) else f 
            for f in unique_files
        ]
    
    @classmethod
    def format_config_file_tuple(cls, 
                                config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None
                                ) -> Optional[Tuple[UPath|str]]:
        """
        Formats the config_files as a tuple for immutability in the parameters.

        Args:
            config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.

        Returns:
            Tuple[UPath|str]: The configuration files as a tuple, or None if not provided.

        """

        if config_files is None:
            return None        

        if isinstance(config_files, (list, tuple)) and len(config_files) == 0:
            return None        

        if isinstance(config_files, (UPath, str)):
            return (config_files,)

        config_files = cls.deduplicate_files(config_files)
        
        return tuple(config_files)    
    


    @classmethod
    def format_config_file_list(cls, 
                                 config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None
                                 ) -> Optional[List[UPath|str]]:
        
        """
        Ensures the config_files are formatted as a list.

        Args:
            config_files (Union[UPath, List[UPath]]): The configuration file or list of configuration files.

        Returns:
            List[UPath|str]: The list of configuration files, or None if not provided
        """


        if config_files is None:
            return None        

        if isinstance(config_files, (list, tuple)) and len(config_files) == 0:
            return None        

        if isinstance(config_files, (UPath, str)):
            return [config_files]

        if isinstance(config_files, (list, tuple)):
            return cls.deduplicate_files(config_files)

        raise ValueError(f"Invalid config_files: {config_files}")
