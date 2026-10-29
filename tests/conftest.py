"""Register shared fixtures; domain-specific setup lives beside its consumers."""

pytest_plugins = (
    "tests.fixtures.cache",
    "tests.fixtures.config_files",
    "tests.fixtures.secret_stores",
)
