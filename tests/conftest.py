import pytest


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """Hashing passwords with the production hasher makes tests slow; MD5 is fine for tests only."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
