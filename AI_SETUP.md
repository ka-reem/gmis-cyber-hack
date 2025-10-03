# AI Integration Setup Guide

## Quick Start

1. **Get your Llama API key** from the Llama API platform

2. **Set the environment variable:**

   **macOS/Linux (bash/zsh):**
   ```bash
   export LLAMA_API_KEY="your_api_key_here"
   ```
   
   **Or add to your shell profile (~/.zshrc or ~/.bashrc):**
   ```bash
   echo 'export LLAMA_API_KEY="your_api_key_here"' >> ~/.zshrc
   source ~/.zshrc
   ```

3. **Install the OpenAI package:**
   ```bash
   pip install openai
   ```

4. **Run the script:**
   ```bash
   python ctf_browser.py
   ```

## How It Works

When you run the script:

1. 🔑 Script checks for `LLAMA_API_KEY` environment variable
2. 🤖 Initializes AI client if key is found
3. 🎯 Clicks each challenge card
4. 📝 Extracts the question text from the modal
5. 💬 Sends question to Llama AI
6. 💡 Displays AI-generated answer
7. ❌ Closes the modal
8. ➡️ Moves to next challenge

## Example Flow

```
🚀 GMIS CTF Browser Automation
========================================
✅ AI client initialized
🔄 Loading saved login state...
🌐 Navigating to: https://2025-gmis-advance.ctfd.io/challenges
⏳ Waiting for security checks to complete...
✅ Security checks completed (or timed out)
⏳ Waiting for page to stabilize...
⏳ Waiting for page to fully load...
⏳ Waiting for dynamic content to load...
🔎 Looking for challenge cards using multiple strategies...
✅ Found 20 elements using: divs with class card
🧭 Total elements to click: 20

➡️ Clicking element #1/20: Basketball1
📝 Question extracted: What is 2+2?
🤖 Asking AI: What is 2+2?...
💡 AI Answer: The answer is 4.
💬 AI suggests: The answer is 4.
✅ Closed modal for: Basketball1

➡️ Clicking element #2/20: Basketball2
📝 Question extracted: What is the capital of France?
🤖 Asking AI: What is the capital of France?...
💡 AI Answer: The capital of France is Paris.
💬 AI suggests: The capital of France is Paris.
✅ Closed modal for: Basketball2
...
```

## Troubleshooting

### AI client not initialized
```
⚠️ LLAMA_API_KEY not found in environment - AI answering disabled
```
**Solution:** Set the `LLAMA_API_KEY` environment variable

### Import error
```
ModuleNotFoundError: No module named 'openai'
```
**Solution:** Run `pip install openai`

### API errors
```
❌ AI error: Invalid API key
```
**Solution:** Check that your API key is correct

## Testing the AI Integration

Test if your API key works:

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("LLAMA_API_KEY"), 
    base_url="https://api.llama.com/compat/v1/"
)

completion = client.chat.completions.create(
    model="Llama-4-Maverick-17B-128E-Instruct-FP8",
    messages=[{"role": "user", "content": "Hello!"}],
)

print(completion.choices[0].message.content)
```

If this works, the integration is set up correctly!

## Customization

You can modify the AI behavior in `ctf_browser.py`:

```python
async def get_ai_answer(self, question_text: str) -> str:
    # Modify the system prompt here
    completion = self.ai_client.chat.completions.create(
        model="Llama-4-Maverick-17B-128E-Instruct-FP8",
        messages=[
            {
                "role": "system",
                "content": "Your custom system prompt here"
            },
            {
                "role": "user",
                "content": question_text
            }
        ],
    )
```
