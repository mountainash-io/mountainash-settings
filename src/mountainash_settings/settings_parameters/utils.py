
from typing import Optional, Union, List, Any, Tuple, Dict

from upath import UPath

from .settings_parameters import SettingsParameters
from .filehandler import SettingsFileHandler
from .kwargshandler import SettingsKwargsHandler
from .merge_framework import get_merger, FieldMergeUtils

class SettingsUtils:

    """
    Utility class for handling settings parameters.
    """

    #Hashable format for settings parameters
    default_namespace: str = "DEFAULT"


    @classmethod
    def merge_settings_parameter_objects(cls,
                        base: SettingsParameters,
                        other: SettingsParameters,
                        prioritise_self: bool = False
                   ) -> SettingsParameters:
        """
        Merge two SettingsParameters objects using the generic merge framework.

        Eliminates ~45 lines of duplicate prioritization logic by delegating
        to the generic merger with proper validation and field-specific strategies.
        """
        merger = get_merger()
        return merger.merge_with_object(
            base=base,
            other=other,
            prioritise_base=prioritise_self
        )

    @classmethod
    def merge_settings_parameters(cls,
                            base: SettingsParameters,
                            namespace: Optional[str] = None,
                            config_files: Optional[Union[UPath, str, List[Union[UPath, str]]]] = None,
                            kwargs: Optional[Dict[str, Any]] = None,
                            env_prefix: Optional[str] = None,
                            secrets_dir: Optional[str] = None,
                            prioritise_self: Optional[bool] = False
               ) -> 'SettingsParameters':
        """
        Merge SettingsParameters with individual parameters using the generic merge framework.

        Eliminates ~30 lines of duplicate prioritization logic by delegating
        to the generic merger with parameter-specific handling.
        """
        merger = get_merger()
        return merger.merge_with_params(
            base=base,
            namespace=namespace,
            config_files=config_files,
            kwargs=kwargs,
            env_prefix=env_prefix,
            secrets_dir=secrets_dir,
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


    # Resolve / Merge values - simplified using FieldMergeUtils
    @staticmethod
    def merge_namespaces(namespace1: Optional[str] = None,
                         namespace2: Optional[str] = None) -> str:
        """Merge namespace strings using the generic merge framework."""
        return FieldMergeUtils.merge_namespaces(namespace1, namespace2)

    @staticmethod
    def merge_env_prefix(env_prefix1: Optional[str] = None,
                         env_prefix2: Optional[str] = None) -> Optional[str]:
        """Merge environment prefix strings using the generic merge framework."""
        return FieldMergeUtils.merge_env_prefixes(env_prefix1, env_prefix2)

    @staticmethod
    def merge_config_files(config_files1: Optional[Tuple[Union[UPath, str], ...]] = None,
                            config_files2: Optional[Tuple[Union[UPath, str], ...]] = None) -> Optional[Tuple[Union[UPath, str], ...]]:
        """Merge config files using the generic merge framework with proper deduplication."""
        return FieldMergeUtils.merge_config_files_simple(config_files1, config_files2)

    @staticmethod
    def merge_kwargs(kwargs1: Optional[Tuple[Tuple[str, Any], ...]] = None,
                      kwargs2: Optional[Tuple[Tuple[str, Any], ...]] = None) -> Optional[Tuple[Tuple[str, Any], ...]]:
        """
        Merge kwargs using the generic merge framework.

        Note: Converts tuple format to dict for processing, then back to maintain compatibility.
        """
        # Convert tuple format to dict format for processing
        dict1 = dict(kwargs1) if kwargs1 else None
        dict2 = dict(kwargs2) if kwargs2 else None

        merged_dict = FieldMergeUtils.merge_kwargs_simple(dict1, dict2)

        # Convert back to tuple format for compatibility
        if merged_dict:
            return tuple(merged_dict.items())
        return None
