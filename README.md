# mountainash-settings

![Python](https://img.shields.io/badge/python-3.12%2B-blue) ![Category](https://img.shields.io/badge/category-core-purple) ![Tests](https://img.shields.io/badge/tests-✓-green) ![Docs](https://img.shields.io/badge/docs-✓-blue)

Advanced configuration management for Python applications with smart caching, template resolution, multi-format support, and seamless Pydantic integration.

## Overview

mountainash-settings provides sophisticated configuration management that goes beyond standard Pydantic BaseSettings. It offers smart caching, template resolution, multi-format configuration files (YAML, TOML, JSON), and a powerful parameter system - all while maintaining the familiar Pydantic interface developers love.



## Installation

```bash
pip install mountainash-settings
```

### Development Installation

```bash
# Clone and install in development mode
git clone <repository-url>
cd mountainash-settings
pip install -e .
```



## Quick Start

### Basic Usage with MountainAshBaseSettings

```python
from pydantic import Field
from mountainash_settings import MountainAshBaseSettings

class AppSettings(MountainAshBaseSettings):
    """Application settings with smart caching and template support."""
    debug: bool = Field(default=False)
    app_name: str = Field(default="MyApp")
    database_url: str = Field(default="sqlite:///app.db")
    log_file: str = Field(default="logs/{app_name}.log")  # Template support

# Simple usage - works like standard Pydantic
settings = AppSettings()
print(settings.app_name)  # "MyApp"

# With runtime overrides
settings = AppSettings(debug=True, app_name="ProductionApp")
print(settings.debug)  # True

# Smart caching with get_settings()
cached_settings = AppSettings.get_settings(
    namespace="production",
    config_files=["config.yaml"],
    debug=True
)

# Template resolution
log_path = settings.format_template_from_settings("logs/{app_name}_debug.log")
print(log_path)  # "logs/ProductionApp_debug.log"
```

### Multi-Format Configuration Files

Create `config.yaml`:
```yaml
debug: false
app_name: "MyWebApp"
database_url: "postgresql://localhost/myapp"
```

```python
from mountainash_settings import MountainAshBaseSettings
from pydantic_settings import SettingsConfigDict

class ConfigSettings(MountainAshBaseSettings):
    debug: bool = Field(default=True)
    app_name: str = Field(default="DefaultApp")
    database_url: str = Field(default="sqlite:///default.db")
    
    model_config = SettingsConfigDict(yaml_file="config.yaml")

settings = ConfigSettings()
print(settings.app_name)  # "MyWebApp" (from YAML file)
```

### Advanced Usage with SettingsParameters

```python
from mountainash_settings import SettingsParameters

# Create reusable parameter configurations
params = SettingsParameters.create(
    namespace="microservice_auth",
    settings_class=AppSettings,
    config_files=["base.yaml", "auth.yaml"],
    env_prefix="AUTH_",
    debug=False,  # Runtime override
    app_name="AuthService"
)

# Use with any compatible settings class
settings = AppSettings.get_settings(settings_parameters=params)
print(settings.app_name)  # "AuthService"
print(settings.SETTINGS_NAMESPACE)  # "microservice_auth"

# Works with any MountainAshBaseSettings class
params = SettingsParameters.create(
    namespace="microservice_auth",
    settings_class=AppSettings,
    config_files=["base.yaml", "auth.yaml"],
    env_prefix="AUTH_",
    debug=False,
    app_name="AuthService"
)
```



## Key Features

### 🎯 **MountainAshBaseSettings** (Primary Interface)
- **Enhanced Pydantic Interface**: Extended BaseSettings with advanced functionality
- **Template Support**: Dynamic field substitution with `{field_name}` placeholders
- **Multi-Format Configuration**: YAML, TOML, JSON support out of the box
- **Smart Caching**: Intelligent instance caching and management

### ⚡ **Smart Caching System**
- **Structural Parameter Caching**: Cache based on namespace, config files, and class structure
- **Runtime Override Support**: Apply kwargs without affecting cache identity
- **Memory Efficient**: Intelligent cache key generation and cleanup
- **Cross-Application Support**: Share cached instances across modules

### 🔧 **Template Resolution** 
- **Dynamic Configuration**: Use `{field_name}` placeholders in any string field
- **Post-Initialization Processing**: Templates resolved automatically after object creation
- **Flexible API**: `format_template_from_settings()` for ad-hoc formatting
- **Custom Logic Support**: Integrate with custom `post_init()` methods

### 📁 **Multi-Format Configuration**
- **Universal Support**: YAML, TOML, JSON, and .env files
- **Priority System**: Hierarchical configuration loading with clear precedence
- **File Validation**: Automatic validation that configuration files exist
- **Environment Integration**: Seamless environment variable support

### 🔄 **SettingsParameters System**
- **Reusable Configuration**: Create parameter objects for consistent settings
- **Dynamic Resolution**: SettingsParameters carry type information for runtime resolution
- **Serialization Safe**: Store and transmit configuration parameters securely
- **JIT Security**: Just-in-time settings loading to minimize secret exposure
- **Complex Scenarios**: Support for multi-tenant and dynamic configuration needs

### 📊 **Metadata Tracking & Observability**
- **Full Traceability**: Track configuration sources, files, and overrides
- **Debugging Support**: Comprehensive metadata for troubleshooting
- **Configuration Audit**: Know exactly where each setting value came from
- **Parameter Reconstruction**: Extract SettingsParameters from any instance

### 🏗️ **Enterprise-Ready Architecture**
- **Authentication Integration**: Built-in support for database, storage, and secret providers
- **Secret Management**: Integration with AWS, Azure, GCP, and HashiCorp Vault
- **Performance Optimized**: Minimal overhead with intelligent caching strategies
- **Production Tested**: Battle-tested in large-scale applications



## Documentation

### 📚 **Core Documentation**
- **[CLAUDE.md](CLAUDE.md)** - Complete development guide and API reference
- **[Examples](examples/)** - Working code examples and patterns
- **[TESTING.md](TESTING.md)** - Testing guidelines and procedures
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines

### 🔧 **Development**
- **[CLAUDE.md](CLAUDE.md)** - Development guide and technical details

### 🌐 **Ecosystem**
- **[Mountain Ash Documentation](https://mountainash-io.github.io/mountainash-docs/)** - Complete ecosystem docs



## Advanced Usage Examples

### Feature-Specific Configurations

```python
from mountainash_settings import MountainAshBaseSettings
from pydantic_settings import SettingsConfigDict

# High-performance service
class HighPerfSettings(MountainAshBaseSettings):
    api_timeout: int = Field(default=5)
    max_connections: int = Field(default=100)

# Complex configuration service with templates
class ComplexAppSettings(MountainAshBaseSettings):
    environment: str = Field(default="dev")
    service_name: str = Field(default="myapp")
    
    # Template-based paths
    log_dir: str = Field(default="logs/{environment}/{service_name}")
    config_file: str = Field(default="config/{service_name}/{environment}.yaml")
    
    model_config = SettingsConfigDict(
        yaml_file=["base.yaml", "{environment}.yaml"],
        env_prefix="APP_"
    )

# Testing settings
class TestSettings(MountainAshBaseSettings):
    test_database: str = Field(default="sqlite:///:memory:")
    mock_external_apis: bool = Field(default=True)
```

### Production Patterns

```python
# Multi-tenant configuration
def create_tenant_settings(tenant_id: str):
    class TenantSettings(MountainAshBaseSettings):
        database_url: str = Field(default="sqlite:///default.db")
        feature_flags: dict = Field(default_factory=dict)
        
        @classmethod
        def get_namespace(cls):
            return f"tenant_{tenant_id}"
    
    return TenantSettings

# Environment-based configuration
class EnvironmentAwareSettings(MountainAshBaseSettings):
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    model_config = SettingsConfigDict(
        yaml_file=[
            "base.yaml",
            f"{os.getenv('ENVIRONMENT', 'dev')}.yaml",
            "local.yaml"  # Optional local overrides
        ]
    )
    
    @classmethod
    def get_namespace(cls):
        return f"app_{os.getenv('ENVIRONMENT', 'dev')}"
```

## Advanced Configuration Patterns

MountainAshBaseSettings provides powerful patterns for complex configuration scenarios:

```python
from mountainash_settings import MountainAshBaseSettings, SettingsParameters

class AppSettings(MountainAshBaseSettings):
    debug: bool = Field(default=False)
    app_name: str = Field(default="MyApp")
    database_url: str = Field(default="sqlite:///app.db")

# Smart caching with SettingsParameters
params = SettingsParameters.create(
    namespace="production",
    settings_class=AppSettings,
    config_files=["config.yaml"],
    debug=True
)

# Cached instance - subsequent calls return same instance
settings = AppSettings.get_settings(settings_parameters=params)
```

**Key Benefits:**
- ✅ **Smart Caching**: Intelligent instance management and caching
- ✅ **Template Support**: Dynamic field substitution
- ✅ **Multi-Format Config**: YAML, TOML, JSON support
- ✅ **Enterprise Ready**: Production-tested performance and features
- ✅ **Full Observability**: Complete configuration traceability

## Development & Testing

### Testing

```bash
# Run all tests
hatch run test:test

# Run with coverage
hatch run test:cov

# Run specific tests
pytest tests/test_base_settings.py -v

# Performance benchmarks
pytest tests/test_base_settings.py::TestBaseSettingsPerformance -v
```

### Linting & Quality

```bash
# Code linting
hatch run ruff:check

# Auto-fix issues
hatch run ruff:fix

# Type checking
hatch run mypy:check
```

### Build Commands

```bash
# Build package
hatch build

# Clean build artifacts
hatch clean
```

See [CLAUDE.md](CLAUDE.md) for complete development commands.

## Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes with tests
4. **Run** tests and linting (`hatch run test:test && hatch run ruff:check`)
5. **Commit** your changes (`git commit -m 'Add amazing feature'`)
6. **Push** to the branch (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Development Setup

```bash
git clone https://github.com/mountainash-io/mountainash-settings.git
cd mountainash-settings
pip install -e .
hatch env create  # Set up development environment
```



## Why Choose mountainash-settings?

### vs Standard Pydantic BaseSettings
- ✅ **Smart Caching**: Automatically cache settings for better performance
- ✅ **Template Support**: Dynamic configuration with `{field}` placeholders  
- ✅ **Multi-Format Files**: YAML, TOML, JSON support out of the box
- ✅ **Configuration Reuse**: SettingsParameters for consistent configuration
- ✅ **Metadata Tracking**: Full observability of configuration sources

### vs Other Configuration Libraries
- ✅ **Pydantic Integration**: Built on Pydantic for validation and type safety
- ✅ **Enterprise Features**: Secret management, authentication, multi-tenancy  
- ✅ **Production Ready**: Battle-tested caching and performance optimizations
- ✅ **Developer Experience**: Familiar interface with powerful features
- ✅ **Incremental Adoption**: Use only the features you need

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Mountain Ash Ecosystem

This package is part of the [Mountain Ash](https://github.com/mountainash-io) ecosystem of Python packages for building production-ready applications.

### Related Packages
- **mountainash-core**: Core utilities and foundations
- **mountainash-auth**: Authentication and authorization 
- **mountainash-data**: Data processing and analysis tools
- **mountainash-api**: API development utilities

---

**Ready to get started?** Check out our [CLAUDE.md](CLAUDE.md) development guide or try the [examples](examples/)!

