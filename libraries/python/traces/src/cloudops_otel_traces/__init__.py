#This file contains init logic for src cloudops OTel traces.
from .tracer import init_tracing, get_tracer

__all__ = ["init_tracing", "get_tracer"]
