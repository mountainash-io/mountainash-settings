
from mountainash_constants import BaseConstant

### Auth Secrets
class CONST_SECRET_PROVIDER_TYPE(BaseConstant):
    """Enumeration for different secret provider types"""
    AZURE_KEYVAULT = "azure_keyvault"
    AWS_SECRETS = "aws_secrets"
    GCP_SECRETS = "gcp_secrets"
    HASHICORP = "hashicorp"
    LOCAL = "local"

class CONST_SECRET_AUTH_METHOD(BaseConstant):
    """Enumeration for authentication methods"""
    SERVICE_PRINCIPAL = "service_principal"
    MANAGED_IDENTITY = "managed_identity"
    CLIENT_SECRET = "client_secret"
    CERTIFICATE = "certificate"
    TOKEN = "token"
    IAM_ROLE = "iam_role"
    KUBERNETES = "kubernetes"

class CONST_SECRET_VERSION_HANDLING(BaseConstant):
    """Enumeration for version handling strategies"""
    LATEST = "latest"
    SPECIFIC = "specific"
    RANGE = "range"
    ALL = "all"

# class CONST_SECRET_ROTATION_POLICY(BaseConstant):
#     """Enumeration for secret rotation policies"""
#     MANUAL = "manual"
#     SCHEDULED = "scheduled"
#     ON_ACCESS = "on_access"
#     NEVER = "never"


class CONST_SECRET_ENCODING(BaseConstant):
    """Base encoding types for secrets"""
    NONE = "none"
    BASE64 = "base64"
    FERNET = "fernet"

class CONST_AWS_SECRET_STAGES(BaseConstant):
    """AWS Secret Version Stages"""
    CURRENT = "AWSCURRENT"
    PENDING = "AWSPENDING"
    PREVIOUS = "AWSPREVIOUS"
    DEPRECATED = "AWSDEPRECATED"    