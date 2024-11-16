#path: mountainash_settings/auth/database/providers/cloud/bigquery.py

from typing import Optional, List, Any, Dict, Tuple
from upath import UPath

from pydantic import Field, field_validator
import json

from mountainash_settings.auth.database.base import BaseDBAuthSettings
from mountainash_settings.auth.database.constants import CONST_DB_PROVIDER_TYPE
from mountainash_settings.auth.database.exceptions import (
    DBAuthValidationError,
    DBAuthConfigError
)

class BigQueryAuthSettings(BaseDBAuthSettings):
    """BigQuery authentication settings"""
    
    PROVIDER_TYPE: str = Field(default=CONST_DB_PROVIDER_TYPE.BIGQUERY)
    
    # Project Settings
    PROJECT_ID: str = Field(...)
    DATASET_ID: Optional[str] = Field(default=None)
    LOCATION: Optional[str] = Field(default=None)
    
    # # Authentication Settings
    SERVICE_ACCOUNT_INFO: Optional[Dict[str, Any]] = Field(default=None)
    SERVICE_ACCOUNT_FILE: Optional[str] = Field(default=None)
    
    # # Client Settings
    # DEFAULT_QUERY_JOB_CONFIG: Optional[Dict[str, Any]] = Field(default=None)
    # MAXIMUM_BYTES_BILLED: Optional[int] = Field(default=None)
    # API_ENDPOINT: Optional[str] = Field(default=None)
    
    # # Performance Settings
    # NUM_RETRIES: int = Field(default=3)
    # RETRIES_WITH_LOGGING: Optional[List[int]] = Field(default=[1, 5, 10])
    
    def __init__(self, 
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 _dummy: Optional[bool] = False,
                 **kwargs) -> None:  
        super().__init__(config_files=config_files, _dummy=_dummy, **kwargs)

    ## Field Validators ##
    @field_validator("PROJECT_ID")
    def validate_project_id(cls, v: str) -> str:
        """Validate GCP project ID format"""
        if not v:
            raise DBAuthValidationError(
                "Project ID is required",
                provider=CONST_DB_PROVIDER_TYPE.BIGQUERY,
                validation_type="project_id"
            )
        
        if not (6 <= len(v) <= 30):
            raise DBAuthValidationError(
                "Project ID must be between 6 and 30 characters",
                provider=CONST_DB_PROVIDER_TYPE.BIGQUERY,
                validation_type="project_id"
            )
            
        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:

        """Initialize provider-specific settings"""
        if self.SERVICE_ACCOUNT_INFO:
            try:
                if isinstance(self.SERVICE_ACCOUNT_INFO, str):
                    self.SERVICE_ACCOUNT_INFO = json.loads(self.SERVICE_ACCOUNT_INFO)
            except json.JSONDecodeError as e:
                raise DBAuthConfigError(
                    f"Invalid service account info JSON: {str(e)}",
                    provider=self.PROVIDER_TYPE
                )

    def get_connection_string(self) -> str:
        """Generate BigQuery connection string"""
        template = "bigquery://{project_id}"
        if self.DATASET_ID:
            template += "/{dataset_id}"
            
        params = []
        if self.LOCATION:
            params.append(f"location={self.LOCATION}")
        
        if params:
            template += "?" + "&".join(params)
            
        return self.format_connection_string(template)

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments for BigQuery"""
        args = {
            "project": self.PROJECT_ID,
            "dataset_id": self.DATASET_ID,
            "location": self.LOCATION,
            # "num_retries": self.NUM_RETRIES
        }
        
        # Add authentication args
        if self.SERVICE_ACCOUNT_INFO:
            args["credentials_info"] = self.SERVICE_ACCOUNT_INFO
        # elif self.SERVICE_ACCOUNT_FILE:
        #     args["credentials_path"] = self.SERVICE_ACCOUNT_FILE
            
        # # Add client configuration
        # if self.DEFAULT_QUERY_JOB_CONFIG:
        #     args["default_query_job_config"] = self.DEFAULT_QUERY_JOB_CONFIG
        # if self.MAXIMUM_BYTES_BILLED:
        #     args["maximum_bytes_billed"] = self.MAXIMUM_BYTES_BILLED
        # if self.API_ENDPOINT:
        #     args["api_endpoint"] = self.API_ENDPOINT
            
        return {k: v for k, v in args.items() if v is not None}

    # def _test_connection(self) -> bool:
    #     """Test BigQuery connection"""
    #     try:
    #         from google.cloud import bigquery
            
    #         client = bigquery.Client(**self.get_connection_args())
            
    #         # Test query
    #         query = "SELECT 1"
    #         job = client.query(query)
    #         job.result()  # Wait for query to complete
            
    #         client.close()
    #         return True
            
    #     except Exception as e:
    #         raise DBAuthConnectionError(
    #             f"Failed to connect to BigQuery: {str(e)}",
    #             provider=self.PROVIDER_TYPE
    #         )