"""Datadog APM trace"""
from functools import wraps
from typing import Callable

from ddtrace import config, patch_all

from config import ENVIRONMENT


def ddog_apm_trace(func: Callable):
    """Configure Datadog APM trace."""

    @wraps(func)
    def wrap(*args, **kwargs):
        config.env = ENVIRONMENT  # the environment the application is in
        config.service = "broiestbot"  # name of your application
        config.version = "0.1.0"  # version of your application
        patch_all()
        return func(*args, **kwargs)

    return wrap
