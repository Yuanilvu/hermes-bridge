"""
Shared rate limiter instance for Hermes Bridge.
Avoids circular imports — server.py and router files both import from here.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["30/minute"],
)
