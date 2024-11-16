#path: mountainash_settings/auth/database/providers/file/sqlite.py

from typing import Optional, List, Any, Dict, Tuple
from upath import UPath

from pydantic import Field, field_validator

from mountainash_settings.auth.database.base import BaseDBAuthSettings
from mountainash_settings.auth.database.constants import (
    CONST_DB_PROVIDER_TYPE
)
from mountainash_settings.auth.database.exceptions import (
    DBAuthValidationError
)

class SQLiteAuthSettings(BaseDBAuthSettings):
    """SQLite authentication settings"""
    
    PROVIDER_TYPE: str = Field(default=CONST_DB_PROVIDER_TYPE.SQLITE.value)
    AUTH_METHOD: str = Field(default="none")  # SQLite uses file-based authentication
    
    # File Settings
    DATABASE_PATH: str = Field(default=None) 
    MODE: str = Field(default="ro")  # ro=readonly, rw=readwrite, rwc=readwrite+create
    URI: bool = Field(default=False)  # Use URI connection string format
    IMMUTABLE: bool = Field(default=False)  # Mark database as immutable
    
    # # Connection Settings
    # ISOLATION_LEVEL: Optional[str] = Field(default=None)  # None=autocommit
    # TIMEOUT: float = Field(default=5.0)  # Connection timeout in seconds
    # CACHE_SIZE: int = Field(default=-2000)  # Default to 2MB cache
    
    # # Performance Settings
    # JOURNAL_MODE: str = Field(default="WAL")  # WAL=write-ahead logging
    # SYNCHRONOUS: str = Field(default="NORMAL")
    # MMAP_SIZE: Optional[int] = Field(default=None)
    
    def __init__(self, 
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 _dummy: Optional[bool] = False,
                 **kwargs) -> None:  
        super().__init__(config_files=config_files, _dummy=_dummy, **kwargs)

    ## Field Validators ##
    @field_validator("MODE")
    def validate_mode(cls, v: str) -> str:
        """Validate SQLite mode"""
        valid_modes = {"ro", "rw", "rwc"}
        if v not in valid_modes:
            raise DBAuthValidationError(
                f"Invalid SQLite mode. Must be one of: {valid_modes}",
                provider=CONST_DB_PROVIDER_TYPE.SQLITE,
                validation_type="mode"
            )
        return v


    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        pass
        # Validate read-only mode requirements
        # if self.MODE == "ro" and not os.path.exists(self.DATABASE_PATH):
        #     raise DBAuthConfigError(
        #         f"Database file does not exist for read-only mode: {self.DATABASE_PATH}",
        #         provider=self.PROVIDER_TYPE
        #     )
            
        # Check write permissions if needed
        # if self.MODE in {"rw", "rwc"}:
        #     try:
        #         parent = UPath(self.DATABASE_PATH).parent
        #         if not os.access(parent, os.W_OK):
        #             raise DBAuthConfigError(
        #                 f"No write permission for directory: {parent}",
        #                 provider=self.PROVIDER_TYPE
        #             )
        #     except Exception as e:
        #         if isinstance(e, DBAuthConfigError):
        #             raise
        #         raise DBAuthConfigError(
        #             f"Failed to check write permissions: {str(e)}",
        #             provider=self.PROVIDER_TYPE
        #         )

    def get_connection_string(self) -> str:
        """Generate SQLite connection string"""
        if self.URI:
            # URI format with parameters
            params = [f"mode={self.MODE}"]
            if self.IMMUTABLE:
                params.append("immutable=1")
            # if self.CACHE_SIZE:
            #     params.append(f"cache=shared")
                
            path = self.DATABASE_PATH.replace("\\", "/")
            return f"sqlite:///file:{path}?{'&'.join(params)}"
        else:
            # Standard format
            return f"sqlite:///{self.DATABASE_PATH}"

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments for SQLite"""
        args = {
            "database": self.DATABASE_PATH,
            # "timeout": self.TIMEOUT
        }
        
        # if self.ISOLATION_LEVEL is not None:
        #     args["isolation_level"] = self.ISOLATION_LEVEL
            
        pragmas = {}
        # if self.JOURNAL_MODE:
        #     pragmas["journal_mode"] = self.JOURNAL_MODE
        # if self.SYNCHRONOUS:
        #     pragmas["synchronous"] = self.SYNCHRONOUS
        # if self.CACHE_SIZE:
        #     pragmas["cache_size"] = self.CACHE_SIZE
        # if self.MMAP_SIZE:
        #     pragmas["mmap_size"] = self.MMAP_SIZE
            
        if pragmas:
            args["pragmas"] = pragmas
            
        return args

    # def _test_connection(self) -> bool:
    #     """Test SQLite connection"""
    #     try:
    #         import sqlite3
            
    #         conn_args = self.get_connection_args()
    #         pragmas = conn_args.pop("pragmas", {})
            
    #         # Attempt connection
    #         conn = sqlite3.connect(**conn_args)
            
    #         # Apply pragmas
    #         with conn:
    #             for pragma, value in pragmas.items():
    #                 conn.execute(f"PRAGMA {pragma} = {value}")
                    
    #             # Test query
    #             conn.execute("SELECT sqlite_version()")
                
    #         conn.close()
    #         return True
            
    #     except Exception as e:
    #         raise DBAuthConnectionError(
    #             f"Failed to connect to SQLite: {str(e)}",
    #             provider=self.PROVIDER_TYPE
    #         )