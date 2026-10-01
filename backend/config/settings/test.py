"""Test settings: fast, deterministic, Postgres-backed."""

from .base import *  # noqa: F401,F403

DEBUG = False

# Override the base SECRET_KEY with one >= 32 chars so SimpleJWT's HS256 signing
# does not emit InsecureKeyLengthWarning during the test suite.
SECRET_KEY = "test-insecure-key-not-for-production-0123456789abcdef"

# Speed up password hashing in tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
