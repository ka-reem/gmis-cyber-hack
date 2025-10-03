# GMIS CTF Browser Automation

This Python script automates opening the GMIS CTF challenges page and maintains your login session between runs using Playwright. **Now with AI-powered question answering!**

## Features

- 🔐 **Login State Persistence**: Saves your login session so you don't need to log in every time
- 🌐 **Automatic Browser Launch**: Opens the CTF challenges page directly
- 🔄 **Session Management**: Intelligently detects if you're already logged in
- ⚡ **Quick Access**: Fast startup for subsequent runs using saved credentials
- 🤖 **AI Question Answering**: Uses Llama AI to analyze and answer CTF questions automatically
- 🎯 **Smart Challenge Detection**: Automatically finds and clicks all challenge cards

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

   Or use the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Set up your API key:**
   ```bash
   export LLAMA_API_KEY="your_api_key_here"
   ```
   
   Or create a `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env and add your LLAMA_API_KEY
   ```

## Usage

### First Run (or when you need to login)
```bash
python ctf_browser.py
```
Log in manually when the browser opens. Your session will be saved automatically.

### Normal Run (uses saved login + AI)
```bash
export LLAMA_API_KEY="your_key"
python ctf_browser.py
```

The script will:
1. Load your saved login session
2. Navigate to the challenges page
3. Find and click each challenge card
4. Extract the question text
5. **Send question to AI and get answer**
6. Display the AI's suggested answer
7. Close the modal and move to next challenge

## How it works

1. **First time**: The script opens a browser window. Log in manually, and your session is saved
2. **After login**: Your session state (cookies, localStorage, etc.) is saved to `browser_state/auth_state.json`
3. **Subsequent runs**: The script automatically loads your saved login state
4. **Challenge clicking**: Automatically detects and clicks all challenge cards
5. **AI answering**: For each challenge:
   - Extracts the question text from the modal
   - Sends it to Llama AI
   - Gets and displays the answer
   - You can review the answer before submitting
6. **Browser stays open**: The browser window remains open until you press `Ctrl+C`

## Command Line Options

### Use Custom Selector
```bash
python ctf_browser.py --selector 'div.challenge-card'
```

### Add Delay Between Clicks
```bash
python ctf_browser.py --delay 1000
```

### Combine Options
```bash
python ctf_browser.py --selector 'div.card' --delay 500
```

## Files Created

- `browser_state/` - Directory containing your saved login session
- `browser_state/auth_state.json` - Your encrypted session data
- `debug_screenshot.png` - Screenshot if no elements found (for debugging)
- `debug_page.html` - Page HTML for debugging selector issues

## CTF Platform

- **URL**: https://2025-gmis-advance.ctfd.io/challenges
- **Target**: GMIS Advance CTF Platform

## AI Integration

The script uses the Llama API to answer questions:
- **Model**: Llama-4-Maverick-17B-128E-Instruct-FP8
- **Purpose**: Analyzes CTF questions and provides answers
- **Output**: Displays AI-suggested answers in the terminal

### Example Output:
```
➡️ Clicking element #1/20: Basketball1
📝 Question extracted: What is the capital of France?
🤖 Asking AI: What is the capital of France?...
💡 AI Answer: The capital of France is Paris.
💬 AI suggests: The capital of France is Paris.
✅ Closed modal for: Basketball1
```

## Troubleshooting

- If login doesn't work, delete the `browser_state/` folder and log in again
- Make sure Playwright browsers are installed with `playwright install`
- If AI isn't working, check that `LLAMA_API_KEY` is set correctly
- If no challenges are found, check `debug_screenshot.png` and `debug_page.html`

## Security Note

Your login session is saved locally in the `browser_state/` directory. Keep this secure and don't share these files. Your LLAMA_API_KEY should also be kept private.