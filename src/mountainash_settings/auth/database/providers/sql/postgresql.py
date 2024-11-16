#path: mountainash_settings/auth/database/providers/sql/postgresql.py


from typing import Optional, List, Any, Dict, Tuple
from upath import UPath

from pydantic import Field
from enum import Enum

from mountainash_settings.auth.database.base import BaseDBAuthSettings
from mountainash_settings.auth.database.constants import (
    CONST_DB_PROVIDER_TYPE
)

class PostgreSQLTargetSessionAttrs(str, Enum):
    """PostgreSQL target session attributes"""
    ANY = "any"
    READ_WRITE = "read-write"
    READ_ONLY = "read-only"
    PRIMARY = "primary"
    STANDBY = "standby"
    PREFER_STANDBY = "prefer-standby"

class PostgreSQLAuthSettings(BaseDBAuthSettings):
    """PostgreSQL authentication settings"""
    
    PROVIDER_TYPE: str = Field(default=CONST_DB_PROVIDER_TYPE.POSTGRESQL)
    PORT: int = Field(default=5432)
    
    # PostgreSQL-specific Settings
    APPLICATION_NAME: Optional[str] = Field(default="MountainAsh")
    OPTIONS: Optional[str] = Field(default=None)
    SEARCH_PATH: Optional[str] = Field(default=None)
    ASYNC_MODE: bool = Field(default=False)
    
    # # Connection Settings
    # KEEPALIVES: bool = Field(default=True)
    # KEEPALIVES_IDLE: Optional[int] = Field(default=None)
    # KEEPALIVES_INTERVAL: Optional[int] = Field(default=None)
    # KEEPALIVES_COUNT: Optional[int] = Field(default=None)
    
    # # Security Settings
    # SSL_MODE: str = Field(default=CONST_DB_SSL_MODE.PREFER)
    # SSL_COMPRESSION: bool = Field(default=True)
    # SSL_MIN_PROTOCOL_VERSION: Optional[str] = Field(default="TLSv1.2")
    # GSS_ENCRYPTION: bool = Field(default=False)
    # KRBSRVNAME: Optional[str] = Field(default="postgres")
    
    # # Session Settings
    # ISOLATION_LEVEL: Optional[str] = Field(default=None)
    # STATEMENT_TIMEOUT: Optional[int] = Field(default=None)
    # LOCK_TIMEOUT: Optional[int] = Field(default=None)
    # IDLE_IN_TRANSACTION_SESSION_TIMEOUT: Optional[int] = Field(default=None)
    
    # # Load Balancing Settings
    # TARGET_SESSION_ATTRS: str = Field(default=PostgreSQLTargetSessionAttrs.ANY)
    # TCP_USER_TIMEOUT: Optional[int] = Field(default=None)
    # LOAD_BALANCE_HOSTS: bool = Field(default=False)
    
    # # Client Encoding Settings
    # CLIENT_ENCODING: Optional[str] = Field(default="UTF8")
    # DATESTYLE: Optional[str] = Field(default="ISO, MDY")
    # TIMEZONE: Optional[str] = Field(default="UTC")

    def __init__(self, 
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 _dummy: Optional[bool] = False,
                 **kwargs) -> None:  
        super().__init__(config_files=config_files, _dummy=_dummy, **kwargs)


    ## Field Validators ##
    # @field_validator("SSL_MODE")
    # def validate_ssl_mode(cls, v: str) -> str:
    #     """Validate SSL mode"""
    #     if v not in CONST_DB_SSL_MODE.__dict__:
    #         raise DBAuthValidationError(
    #             f"Invalid SSL mode",
    #             provider=CONST_DB_PROVIDER_TYPE.POSTGRESQL,
    #             validation_type="ssl_mode"
    #         )
    #     return v

    # @field_validator("ISOLATION_LEVEL")
    # def validate_isolation_level(cls, v: Optional[str]) -> Optional[str]:
    #     """Validate isolation level"""
    #     if v is not None:
    #         valid_levels = {
    #             "READ UNCOMMITTED", 
    #             "READ COMMITTED", 
    #             "REPEATABLE READ", 
    #             "SERIALIZABLE"
    #         }
    #         if v.upper() not in valid_levels:
    #             raise DBAuthValidationError(
    #                 f"Invalid isolation level. Must be one of: {valid_levels}",
    #                 provider=CONST_DB_PROVIDER_TYPE.POSTGRESQL,
    #                 validation_type="isolation_level"
    #             )
    #     return v
        
    # @field_validator("TARGET_SESSION_ATTRS")
    # def validate_target_session_attrs(cls, v: str) -> str:
    #     """Validate target session attributes"""
    #     try:
    #         return PostgreSQLTargetSessionAttrs(v)
    #     except ValueError:
    #         raise DBAuthValidationError(
    #             f"Invalid target session attributes. Must be one of: {[e.value for e in PostgreSQLTargetSessionAttrs]}",
    #             provider=CONST_DB_PROVIDER_TYPE.POSTGRESQL,
    #             validation_type="target_session_attrs"
    #         )

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        pass
        
        # # Validate SSL configuration
        # if self.SSL_MODE != CONST_DB_SSL_MODE.DISABLED:
        #     if self.SSL_MODE in {CONST_DB_SSL_MODE.VERIFY_CA, CONST_DB_SSL_MODE.VERIFY_FULL}:
        #         if not self.SSL_CA:
        #             raise DBAuthConfigError(
        #                 f"CA certificate required for SSL mode: {self.SSL_MODE}",
        #                 provider=self.PROVIDER_TYPE
        #             )
                    
        # # Validate GSS encryption settings
        # if self.GSS_ENCRYPTION and not self.KRBSRVNAME:
        #     raise DBAuthConfigError(
        #         "KRBSRVNAME is required when GSS encryption is enabled",
        #         provider=self.PROVIDER_TYPE
        #     )

    def get_connection_string(self) -> str:
        """Generate PostgreSQL connection string"""
        template = "postgresql://{username}:{password}@{host}:{port}/{database}"
        
        params = []
        
        # # Add SSL parameters
        # if self.SSL_MODE != CONST_DB_SSL_MODE.DISABLED:
        #     params.append(f"sslmode={self.SSL_MODE}")
        #     if self.SSL_CA:
        #         params.append(f"sslcert={self.SSL_CERT}")
        #     if self.SSL_CERT:
        #         params.append(f"sslkey={self.SSL_KEY}")
        #     if self.SSL_COMPRESSION:
        #         params.append("sslcompression=1")
        #     if self.SSL_MIN_PROTOCOL_VERSION:
        #         params.append(f"ssl_min_protocol_version={self.SSL_MIN_PROTOCOL_VERSION}")
                
        # Add application name
        if self.APPLICATION_NAME:
            params.append(f"application_name={self.APPLICATION_NAME}")
            
        # # Add keepalive settings
        # if self.KEEPALIVES:
        #     if self.KEEPALIVES_IDLE:
        #         params.append(f"keepalives_idle={self.KEEPALIVES_IDLE}")
        #     if self.KEEPALIVES_INTERVAL:
        #         params.append(f"keepalives_interval={self.KEEPALIVES_INTERVAL}")
        #     if self.KEEPALIVES_COUNT:
        #         params.append(f"keepalives_count={self.KEEPALIVES_COUNT}")
                
        # # Add timeout settings
        # if self.STATEMENT_TIMEOUT:
        #     params.append(f"statement_timeout={self.STATEMENT_TIMEOUT}")
        # if self.LOCK_TIMEOUT:
        #     params.append(f"lock_timeout={self.LOCK_TIMEOUT}")
        # if self.IDLE_IN_TRANSACTION_SESSION_TIMEOUT:
        #     params.append(f"idle_in_transaction_session_timeout={self.IDLE_IN_TRANSACTION_SESSION_TIMEOUT}")
            
        # # Add load balancing settings
        # if self.TARGET_SESSION_ATTRS:
        #     params.append(f"target_session_attrs={self.TARGET_SESSION_ATTRS}")
        # if self.TCP_USER_TIMEOUT:
        #     params.append(f"tcp_user_timeout={self.TCP_USER_TIMEOUT}")
        # if self.LOAD_BALANCE_HOSTS:
        #     params.append("load_balance_hosts=1")
            
        # # Add encoding settings
        # if self.CLIENT_ENCODING:
        #     params.append(f"client_encoding={self.CLIENT_ENCODING}")
        # if self.DATESTYLE:
        #     params.append(f"datestyle={self.DATESTYLE}")
        # if self.TIMEZONE:
        #     params.append(f"timezone={self.TIMEZONE}")
            
        # # Add other settings
        # if self.OPTIONS:
        #     params.append(f"options={self.OPTIONS}")
            
        if params:
            template += "?" + "&".join(params)
            
        return self.format_connection_string(template)

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments for PostgreSQL"""
        args = super().get_connection_args()
        
        # Add PostgreSQL-specific arguments
        args.update({
            "application_name": self.APPLICATION_NAME,
            # "keepalives": self.KEEPALIVES,
            "async_": self.ASYNC_MODE,  # Note the underscore
        })
        
        # Add optional arguments
        if self.OPTIONS:
            args["options"] = self.OPTIONS
        if self.SEARCH_PATH:
            args["options"] = f"-c search_path={self.SEARCH_PATH}"
        # if self.ISOLATION_LEVEL:
        #     args["isolation_level"] = self.ISOLATION_LEVEL
            
        # Add keepalive settings
        # if self.KEEPALIVES:
        #     if self.KEEPALIVES_IDLE:
        #         args["keepalives_idle"] = self.KEEPALIVES_IDLE
        #     if self.KEEPALIVES_INTERVAL:
        #         args["keepalives_interval"] = self.KEEPALIVES_INTERVAL
        #     if self.KEEPALIVES_COUNT:
        #         args["keepalives_count"] = self.KEEPALIVES_COUNT
                
        # # Add timeout settings
        # if self.STATEMENT_TIMEOUT:
        #     args["statement_timeout"] = self.STATEMENT_TIMEOUT
        # if self.LOCK_TIMEOUT:
        #     args["lock_timeout"] = self.LOCK_TIMEOUT
        # if self.IDLE_IN_TRANSACTION_SESSION_TIMEOUT:
        #     args["idle_in_transaction_session_timeout"] = self.IDLE_IN_TRANSACTION_SESSION_TIMEOUT
        # if self.TCP_USER_TIMEOUT:
        #     args["tcp_user_timeout"] = self.TCP_USER_TIMEOUT
            
        # # Add SSL configuration
        # if self.SSL_MODE != CONST_DB_SSL_MODE.DISABLED:
        #     args["sslmode"] = self.SSL_MODE
        #     if self.SSL_CA:
        #         args["sslcert"] = self.SSL_CERT
        #     if self.SSL_CERT:
        #         args["sslkey"] = self.SSL_KEY
        #     args["sslcompression"] = self.SSL_COMPRESSION
        #     if self.SSL_MIN_PROTOCOL_VERSION:
        #         args["ssl_min_protocol_version"] = self.SSL_MIN_PROTOCOL_VERSION
            
        # # Add GSS encryption settings
        # if self.GSS_ENCRYPTION:
        #     args["gssencmode"] = "require"
        #     args["krbsrvname"] = self.KRBSRVNAME
            
        # # Add load balancing settings
        # if self.TARGET_SESSION_ATTRS:
        #     args["target_session_attrs"] = self.TARGET_SESSION_ATTRS
        # if self.LOAD_BALANCE_HOSTS:
        #     args["load_balance_hosts"] = True
            
        # # Add encoding settings
        # if self.CLIENT_ENCODING:
        #     args["client_encoding"] = self.CLIENT_ENCODING
        # if self.DATESTYLE:
        #     args["datestyle"] = self.DATESTYLE
        # if self.TIMEZONE:
        #     args["timezone"] = self.TIMEZONE
            
        return {k: v for k, v in args.items() if v is not None}

    # def _test_connection(self) -> bool:
    #     """Test PostgreSQL connection"""
    #     try:
    #         import psycopg2
            
    #         conn = psycopg2.connect(**self.get_connection_args())
    #         with conn.cursor() as cursor:
    #             cursor.execute("SELECT version()")
    #             version = cursor.fetchone()[0]
                
    #             # Test search path if specified
    #             if self.SEARCH_PATH:
    #                 cursor.execute("SHOW search_path")
    #                 search_path = cursor.fetchone()[0]
    #                 if self.SEARCH_PATH not in search_path:
    #                     raise DBAuthConfigError(
    #                         f"Search path validation failed. Expected: {self.SEARCH_PATH}, Got: {search_path}",
    #                         provider=self.PROVIDER_TYPE
    #                     )
                
    #             # Test SSL if enabled
    #             if self.SSL_MODE != CONST_DB_SSL_MODE.DISABLED:
    #                 cursor.execute("SHOW ssl")
    #                 ssl_enabled = cursor.fetchone()[0]
    #                 if ssl_enabled != "on":
    #                     raise DBAuthConfigError(
    #                         "SSL is not enabled on the connection",
    #                         provider=self.PROVIDER_TYPE
    #                     )
            
    #         conn.close()
    #         return True
            
    #     except Exception as e:
    #         raise DBAuthConnectionError(
    #             f"Failed to connect to PostgreSQL: {str(e)}",
    #             provider=self.PROVIDER_TYPE
    #         )