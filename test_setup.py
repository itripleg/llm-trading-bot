#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test that all project dependencies and configuration work correctly
"""

import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
os.environ['PYTHONIOENCODING'] = 'utf-8'

print("=" * 60)
print("ALPHA ARENA MINI - Dependency & Setup Test")
print("=" * 60)
print()

# Test Python version
print(f"[OK] Python Version: {sys.version.split()[0]}")
assert sys.version_info >= (3, 10), "Python 3.10+ required"
print()

# Test core dependencies
print("Testing core dependencies:")
try:
    import pandas as pd
    print(f"  [OK] pandas {pd.__version__}")
except ImportError as e:
    print(f"  [FAIL] pandas import failed: {e}")
    sys.exit(1)

try:
    import numpy as np
    print(f"  [OK] numpy {np.__version__}")
except ImportError as e:
    print(f"  [FAIL] numpy import failed: {e}")
    sys.exit(1)

try:
    import ccxt
    print(f"  [OK] ccxt {ccxt.__version__}")
except ImportError as e:
    print(f"  [FAIL] ccxt import failed: {e}")
    sys.exit(1)

try:
    import pandas_ta
    print(f"  [OK] pandas_ta")
except ImportError as e:
    print(f"  [FAIL] pandas_ta import failed: {e}")
    sys.exit(1)

print()

# Test LLM dependencies
print("Testing LLM dependencies:")
try:
    import anthropic
    print(f"  [OK] anthropic {anthropic.__version__}")
except ImportError as e:
    print(f"  [FAIL] anthropic import failed: {e}")
    sys.exit(1)

try:
    import openai
    print(f"  [OK] openai {openai.__version__}")
except ImportError as e:
    print(f"  [FAIL] openai import failed: {e}")
    sys.exit(1)

print()

# Test utility dependencies
print("Testing utility dependencies:")
try:
    from pydantic import BaseModel, Field
    print(f"  [OK] pydantic (with BaseModel, Field)")
except ImportError as e:
    print(f"  [FAIL] pydantic import failed: {e}")
    sys.exit(1)

try:
    from pydantic_settings import BaseSettings
    print(f"  [OK] pydantic_settings (with BaseSettings)")
except ImportError as e:
    print(f"  [FAIL] pydantic_settings import failed: {e}")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    print(f"  [OK] python_dotenv (with load_dotenv)")
except ImportError as e:
    print(f"  [FAIL] python_dotenv import failed: {e}")
    sys.exit(1)

try:
    from tenacity import retry
    print(f"  [OK] tenacity (with retry)")
except ImportError as e:
    print(f"  [FAIL] tenacity import failed: {e}")
    sys.exit(1)

print()

# Test web dependencies
print("Testing web dependencies:")
try:
    import flask
    print(f"  [OK] flask {flask.__version__}")
except ImportError as e:
    print(f"  [FAIL] flask import failed: {e}")
    sys.exit(1)

try:
    import flask_cors
    print(f"  [OK] flask_cors")
except ImportError as e:
    print(f"  [FAIL] flask_cors import failed: {e}")
    sys.exit(1)

print()

# Test testing dependencies
print("Testing test dependencies:")
try:
    import pytest
    print(f"  [OK] pytest {pytest.__version__}")
except ImportError as e:
    print(f"  [FAIL] pytest import failed: {e}")
    sys.exit(1)

print()

# Test project structure
print("Checking project structure:")
required_dirs = ["config", "data", "llm", "trading", "agents", "orchestrator", "analysis", "logs", "tests"]
for d in required_dirs:
    if Path(d).is_dir():
        print(f"  [OK] {d}/")
    else:
        print(f"  [FAIL] {d}/ NOT FOUND")
        sys.exit(1)

print()

# Check for configuration files
print("Checking configuration files:")
config_files = [".env.example", "requirements.txt"]
for f in config_files:
    if Path(f).is_file():
        print(f"  [OK] {f}")
    else:
        print(f"  [FAIL] {f} NOT FOUND")
        sys.exit(1)

print()
print("=" * 60)
print("[OK] All tests passed! Setup is complete.")
print("=" * 60)
print()
print("Next steps:")
print("  1. Copy .env.example to .env")
print("  2. Add your API keys to .env")
print("  3. Start with config/settings.py (Phase 1, Task 1.3)")
print()
