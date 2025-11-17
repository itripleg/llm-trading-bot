# LLM Trading Bot Frontend

A modern Next.js dashboard for monitoring the LLM Trading Bot's autonomous trading performance on Hyperliquid.

## New Architecture 🎯

**The bot now POSTS data TO motherhaven, eliminating the need for Flask/SQLite:**

\`\`\`
Python Bot (anywhere) → POST → Next.js API → Firebase
                                       ↓
                            Next.js Frontend ← Firebase
\`\`\`

### Benefits
- ✅ **No Flask server needed** - Bot just POSTs data
- ✅ **Bot runs anywhere** - Local, cloud, VPS, your laptop
- ✅ **HTTPS endpoints** - Secure \`https://motherhaven.app/api/...\`
- ✅ **Firebase storage** - Real-time, scalable, integrated
- ✅ **Simple deployment** - Bot only needs API key

## Quick Start

1. **Set API key** in \`.env\`:
   \`\`\`bash
   LLM_BOT_API_KEY=your-secret-api-key
   \`\`\`

2. **Configure bot** to use \`MotherhavenLogger\`:
   \`\`\`python
   from web.motherhaven_logger import MotherhavenLogger
   
   logger = MotherhavenLogger(
       api_url="https://motherhaven.app",
       api_key="your-secret-api-key"
   )
   \`\`\`

3. **Run bot** - it will POST data automatically

4. **View dashboard** at \`/llm-bot\`

See full documentation below for details.
