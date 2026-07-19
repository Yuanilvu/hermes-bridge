"""
Shared rate limiter instance for Hermes Bridge.
Loads limits from config (env var / settings.toml).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from config_loader import config

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[config.rate_limit.default],
)
