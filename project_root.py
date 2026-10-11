"""
Project Root Path - Single Source of Truth

This module provides a centralized, canonical definition of the project root directory.
All modules should import PROJECT_ROOT from here instead of computing it locally.

Standards compliance:
- PEP 8: Module-level constant in UPPER_CASE
- Uses pathlib.Path for modern, cross-platform path handling
- Computed once at import time for consistency
- Absolute path resolution prevents ambiguity

Usage:
    from project_root import PROJECT_ROOT
    
    config_path = PROJECT_ROOT / "config" / "settings.json"
    data_dir = PROJECT_ROOT / "data"
"""

from pathlib import Path

# Canonical project root: parent directory of this module
# This file is at project root, so parent of this file is the project root
PROJECT_ROOT = Path(__file__).resolve().parent

__all__ = ['PROJECT_ROOT']
