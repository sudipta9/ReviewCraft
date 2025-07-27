# OpenRouter Integration Setup Guide

## Quick Start

1. **Get OpenRouter API Key**
   - Sign up at https://openrouter.ai/
   - Get your API key from the dashboard
   - Free tier includes access to several models including `qwen/qwen3-coder:free`

2. **Set Environment Variables**
   ```bash
   export OPENROUTER_API_KEY="your_api_key_here"
   export AI_USE_OPENROUTER=true
   export AI_OPENROUTER_MODEL="qwen/qwen3-coder:free"
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Available Models

### Free Models
- `qwen/qwen3-coder:free` - Excellent for code analysis (RECOMMENDED)
- `qwen/qwen3-235b-a22b-2507:free` - General purpose

### Paid Models (Cost-effective)
- `qwen/qwen3-coder:free` - Free model for code analysis
- `anthropic/claude-3-haiku` - $0.25/1M input tokens

## Features Enabled

✅ **LLM-Powered Code Analysis**
- Real code quality assessment
- Security vulnerability detection  
- Intelligent code suggestions
- Language-specific analysis

✅ **Semantic Code Analysis**
- Code similarity detection
- Duplicate finding using embeddings
- Semantic search capabilities
- Local processing (no API calls)

## Configuration Options

```bash
# OpenRouter (Primary - ENABLED by default)
OPENROUTER_API_KEY=your_key
AI_OPENROUTER_MODEL=qwen/qwen3-coder:free
```

## Testing the Integration

Run the test to verify everything works:
```bash
python -c "
from app.services.ai_agent import AIAgent
import asyncio

async def test():
    agent = AIAgent()
    result = await agent.analyze_code_quality('def hello(): print(\"world\")', 'test.py')
    print('✅ Integration working!', result.get('language'))

asyncio.run(test())
"
```

## Next Steps

1. Get your OpenRouter API key
2. Set the environment variable
3. Run the system to see AI-powered analysis in action!

The system will automatically fall back to basic analysis if the API key is not configured.
