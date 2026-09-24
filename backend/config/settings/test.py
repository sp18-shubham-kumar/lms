"""Test settings: fast, deterministic, Postgres-backed."""

from .base import *  # noqa: F401,F403

DEBUG = False

# Speed up password hashing in tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
