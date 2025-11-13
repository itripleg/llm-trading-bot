# Quick Start Guide - Alpha Arena Mini

Get up and running in 15 minutes. Follow these exact steps.

## Prerequisites

- Python 3.10 or higher installed
- Git installed
- Hyperliquid account (optional for Phase 1)
- Claude/GPT API key (optional for Phase 1)

## Step 1: Clone & Navigate (1 minute)

```bash
# If starting fresh
cd E:\Github
git clone <your-repo-url> alpha-arena-mini
cd alpha-arena-mini

# If you already have the folder
cd E:\Github\alpha-arena-mini
```

## Step 2: Virtual Environment (2 minutes)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate

# You should see (venv) in your terminal prompt
```

## Step 3: Install Dependencies (3 minutes)

First, create `requirements.txt`:

```bash
# Create the file (or copy from PROJECT_PLAN.md)
# Windows:
notepad requirements.txt

# Mac/Linux:
nano requirements.txt
```

Paste this content:
```txt
ccxt>=4.0.0
pandas>=2.0.0
pandas-ta>=0.3.14b
anthropic>=0.25.0
openai>=1.0.0
python-dotenv>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
tenacity>=8.2.0
coloredlogs>=15.0
```

Install:
```bash
pip install -r requirements.txt

# This may take 2-3 minutes
```

## Step 4: Environment Setup (2 minutes)

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your values
# Windows:
notepad .env

# Mac/Linux:
nano .env
```

**For Phase 1 testing, you can use dummy values:**
```bash
TRADING_MODE=paper
MAX_POSITION_SIZE_USD=50
MAX_LEVERAGE=5
DAILY_LOSS_LIMIT_USD=20
LOG_LEVEL=INFO

# Leave API keys empty for now - we'll add them later
HYPERLIQUID_API_KEY=
ANTHROPIC_API_KEY=
```

## Step 5: Create Directory Structure (2 minutes)

```bash
# Create all directories at once
mkdir -p config data llm trading agents orchestrator analysis logs tests

# Create __init__.py files to make them Python packages
# Windows (PowerShell):
New-Item -ItemType File config/__init__.py
New-Item -ItemType File data/__init__.py
New-Item -ItemType File llm/__init__.py
New-Item -ItemType File trading/__init__.py
New-Item -ItemType File agents/__init__.py
New-Item -ItemType File orchestrator/__init__.py
New-Item -ItemType File analysis/__init__.py
New-Item -ItemType File tests/__init__.py

# Mac/Linux:
touch config/__init__.py data/__init__.py llm/__init__.py trading/__init__.py
touch agents/__init__.py orchestrator/__init__.py analysis/__init__.py tests/__init__.py

# Create .gitkeep for logs directory
# Windows:
New-Item -ItemType File logs/.gitkeep

# Mac/Linux:
touch logs/.gitkeep
```

## Step 6: Create Your First Module (5 minutes)

Let's create `config/settings.py`:

```bash
# Windows:
notepad config/settings.py

# Mac/Linux:
nano config/settings.py
```

Paste this code:
```python
"""Configuration management"""
import os
from enum import Enum
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"

class Settings(BaseSettings):
    # Trading
    trading_mode: TradingMode = Field(default=TradingMode.PAPER)
    max_position_size_usd: float = Field(default=50.0)
    max_leverage: int = Field(default=5)
    daily_loss_limit_usd: float = Field(default=20.0)
    
    # API Keys (optional for Phase 1)
    hyperliquid_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    
    # Execution
    execution_interval_seconds: int = Field(default=180)
    trading_assets: list[str] = Field(default=["BTC/USD:USD", "ETH/USD:USD", "SOL/USD:USD"])
    
    # Logging
    log_level: str = Field(default="INFO")
    log_dir: str = Field(default="./logs")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Singleton
settings = Settings()
```

## Step 7: Test Your Setup (2 minutes)

Create a test file:

```bash
# Windows:
notepad test_setup.py

# Mac/Linux:
nano test_setup.py
```

Paste this:
```python
"""Test that everything is set up correctly"""
from config.settings import settings, TradingMode

print("=" * 50)
print("ALPHA ARENA MINI - Setup Test")
print("=" * 50)
print(f"✅ Config loaded successfully!")
print(f"Trading Mode: {settings.trading_mode}")
print(f"Max Position: ${settings.max_position_size_usd}")
print(f"Assets: {settings.trading_assets}")
print(f"Log Level: {settings.log_level}")
print("=" * 50)

if settings.trading_mode == TradingMode.PAPER:
    print("✅ PAPER MODE - Safe to develop")
else:
    print("⚠️  LIVE MODE - Be careful!")

print("\nSetup complete! Ready for Phase 1 development.")
```

Run it:
```bash
python test_setup.py

# You should see:
# ==================================================
# ALPHA ARENA MINI - Setup Test
# ==================================================
# ✅ Config loaded successfully!
# Trading Mode: paper
# Max Position: $50.0
# Assets: ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD']
# Log Level: INFO
# ==================================================
# ✅ PAPER MODE - Safe to develop
#
# Setup complete! Ready for Phase 1 development.
```

## ✅ You're Ready!

If you see the success message above, you're all set!

## What's Next?

### Option 1: Continue Setup (Recommended)
Follow `.progress/PROJECT_PLAN.md` Phase 1 tasks to build the data pipeline.

### Option 2: Read Documentation
- Read `.progress/START_HERE.md` for full context
- Read `README.md` for project overview
- Read `.progress/PROMPT.md` if you're an AI agent

### Option 3: Start Coding
Jump into Phase 1, Task 1.4: Create `data/fetcher.py` to fetch market data.

## Common Issues

### Issue: `ModuleNotFoundError: No module named 'pydantic_settings'`
**Solution**: 
```bash
pip install pydantic-settings
```

### Issue: Virtual environment not activating
**Solution (Windows)**:
```bash
# If PowerShell, you may need to allow scripts
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: `ta-lib` won't install
**Solution**: Use `pandas-ta` instead (already in requirements.txt)

### Issue: Can't find Python
**Solution**: 
```bash
# Try python3 instead of python
python3 --version
python3 -m venv venv
```

## Verification Checklist

Before moving on, verify:
- [ ] Virtual environment activated (see `(venv)` in terminal)
- [ ] All dependencies installed (`pip list` shows them)
- [ ] `.env` file created (even with empty values)
- [ ] Directory structure created
- [ ] `test_setup.py` runs successfully
- [ ] Trading mode is `paper`

## Ready to Build!

Now that setup is complete, you have two options:

1. **Follow the detailed plan**: `.progress/PROJECT_PLAN.md`
2. **Follow the quick guide**: Continue with Phase 1 tasks

**Next immediate task**: Create `data/fetcher.py` to fetch market data from Hyperliquid.

See `.progress/PROJECT_PLAN.md` Phase 1, Task 1.4 for details.

---

**Having issues?** Check `.progress/START_HERE.md` for troubleshooting.

**Questions about what to build?** Read `README.md` for project goals.

Good luck! 🚀
