
from typing import Optional, Union, List, Any, Tuple, Dict

from upath import UPath

from .settings_parameters import SettingsParameters
from .filehandler import SettingsFileHandler
from .kwargshandler import SettingsKwargsHandler

class SettingsUtils:

    """
    Utility class for handling settings parameters.
    """

    @classmethod
    def merge_settings_parameter_objects(cls,
                        base: SettingsParameters,
                        other: SettingsParameters,
                        prioritise_self: bool = False
                   ) -> SettingsParameters:
        """
        Merge two SettingsParameters objects.

        Delegates to SettingsParameters.merge() classmethod.
        """
        return SettingsParameters.merge(
            base=base,
            other=other,
            prioritise_base=prioritise_self
        )

    @classmethod
    def merge_settings_parameters(cls,
                            base: SettingsParameters,
                            config_files: Optional[Union[UPath, str, List[Union[UPath, str]]]] = None,
                            kwargs: Optional[Dict[str, Any]] = None,
                            env_prefix: Optional[str] = None,
                            secrets_dir: Optional[str] = None,
                            prioritise_self: Optional[bool] = False
               ) -> 'SettingsParameters':
        """
        Merge SettingsParameters with individual parameters.

        Creates a SettingsParameters from the individual params and delegates
        to SettingsParameters.merge().
        """
        other = SettingsParameters.create(
            config_files=config_files,
            env_prefix=env_prefix,
            secrets_dir=secrets_dir,
            **(kwargs or {})
        )
        return SettingsParameters.merge(
            base=base,
            other=other,
            prioritise_base=prioritise_self
        )



    #Translation functions between mutable and immutable

    ############################################################################################################
    # Parameter formatting

    @staticmethod
    def format_kwargs_dict(
                            p_kwargs: None | Dict[str,Any] | Tuple[Any,Any] = None
                            ) -> Optional[Dict[str,Any]]:

        return SettingsKwargsHandler.format_kwargs_dict(p_kwargs=p_kwargs)


    @staticmethod
    def format_kwargs_tuple(
                            p_kwargs: None | Dict[str,Any] | Tuple[Any,Any]  = None
                            ) -> Optional[Tuple[Any,Any]]:

        return SettingsKwargsHandler.format_kwargs_tuple(p_kwargs=p_kwargs)



    @staticmethod
    def format_config_file_list(
                                 config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None
                                 ) -> Optional[List[UPath|str]]:

        return SettingsFileHandler.format_config_file_list(config_files=config_files)


    @staticmethod
    def format_config_file_tuple(
                                config_files: Optional[Union[UPath, str, List[UPath|str], Tuple[UPath|str]]]  = None
                                ) -> Optional[Tuple[UPath|str]]:

        return SettingsFileHandler.format_config_file_tuple(config_files=config_files)


    # Resolve / Merge values

    @staticmethod
    def merge_env_prefix(env_prefix1: Optional[str] = None,
                         env_prefix2: Optional[str] = None) -> Optional[str]:
        """Merge environment prefix strings. First non-None wins."""
        return env_prefix1 or env_prefix2

    @staticmethod
    def merge_config_files(config_files1: Optional[Tuple[Union[UPath, str], ...]] = None,
                            config_files2: Optional[Tuple[Union[UPath, str], ...]] = None) -> Optional[Tuple[Union[UPath, str], ...]]:
        """Merge config files with deduplication."""
        if config_files1 is None and config_files2 is None:
            return None
        merged = set(config_files1 or ()) | set(config_files2 or ())
        return tuple(sorted(str(p) for p in merged)) if merged else None

    @staticmethod
    def merge_kwargs(kwargs1: Optional[Tuple[Tuple[str, Any], ...]] = None,
                      kwargs2: Optional[Tuple[Tuple[str, Any], ...]] = None) -> Optional[Tuple[Tuple[str, Any], ...]]:
        """
        Merge kwargs tuples. Second takes precedence for shared keys.
        """
        dict1 = dict(kwargs1) if kwargs1 else None
        dict2 = dict(kwargs2) if kwargs2 else None

        if dict1 is None and dict2 is None:
            return None

        merged_dict = dict(dict1 or {}) | dict(dict2 or {})
        merged_dict = merged_dict.get("kwargs", merged_dict)

        if merged_dict:
            return tuple(merged_dict.items())
        return None
