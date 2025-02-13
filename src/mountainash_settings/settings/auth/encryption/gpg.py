from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from upath import UPath
from pydantic import Field


from mountainash_settings import SettingsParameters, MountainAshBaseSettings

class GPGAuthSettings(MountainAshBaseSettings, ABC):
    """Base class for database authentication settings"""
    
    # Provider Configuration
    PROVIDER_TYPE: str = Field(...)
    
    # Connection Settings
    GPG_KEY_FILE: Optional[str] = Field(default=None)
    
    

    def __init__(self, 
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                #  _dummy: Optional[bool] = False,
                 **kwargs) -> None:  
        

        super().__init__(config_files=config_files, 
                         settings_parameters=settings_parameters,
                        #  _dummy=_dummy, 
                         **kwargs)

    ########################
    #Single Field Validators




    ########################
    # Post init template parameters

    ########################
    # Abstract Methods
    @abstractmethod
    def _post_init(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        pass

    # @abstractmethod
    # def get_connection_string(self, variant: Optional[str]) -> str:
    #     """Generate connection string from settings"""
    #     pass

    @abstractmethod
    def get_connection_string_template(self, scheme: Optional[str] = None) -> str:
        """Get connection arguments as dictionary"""
        ...


    @abstractmethod
    def get_connection_string_params(self) -> Dict[str, Any]:
        """Get connection string params as a dictionary"""
        ...

    @abstractmethod
    def get_connection_kwargs(self, db_abstraction_layer: Optional[str] = None) -> Dict[str, Any]:

        """Get connection arguments as dictionary"""
        ...

    @abstractmethod
    def get_post_connection_options(self, db_abstraction_layer: Optional[str] = None) -> Dict[str, Any]:

        """Get connection arguments as dictionary"""
        ...




