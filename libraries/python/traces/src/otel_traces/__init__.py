#This file contains init logic for the otel traces library.
from .tracer import init, get_tracer

__all__ = ["init", "get_tracer"]
