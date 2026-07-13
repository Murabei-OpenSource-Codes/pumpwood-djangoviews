"""Centralize definition of configurations using env variables."""
import os


INFO_CACHE_EXPIRATION = int(
    os.getenv('PUMPWOOD_DJANGOVIEWS__INFO_CACHE_EXPIRATION', 600))
"""Config variable to ser cache associated with information data, such as
   options and points."""
