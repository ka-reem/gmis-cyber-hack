# GMIS CTF Browser Automation

This Python script automates opening the GMIS CTF challenges page and maintains your login session between runs using Playwright.

## Features

- 🔐 **Login State Persistence**: Saves your login session so you don't need to log in every time
- 🌐 **Automatic Browser Launch**: Opens the CTF challenges page directly
- 🔄 **Session Management**: Intelligently detects if you're already logged in
- ⚡ **Quick Access**: Fast startup for subsequent runs using saved credentials

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

## Usage

### First Run (or when you need to login)
```bash
python ctf_browser.py --login
```

### Normal Run (uses saved login)
```bash
python ctf_browser.py
```

## How it works

1. **First time**: The script opens a browser window and prompts you to log in manually
2. **After login**: Your session state (cookies, localStorage, etc.) is saved to `browser_state/auth_state.json`
3. **Subsequent runs**: The script automatically loads your saved login state
4. **Browser stays open**: The browser window remains open until you press `Ctrl+C`

## Files Created

- `browser_state/` - Directory containing your saved login session
- `browser_state/auth_state.json` - Your encrypted session data

## CTF Platform

- **URL**: https://2025-gmis-advance.ctfd.io/challenges
- **Target**: GMIS Advance CTF Platform

## Troubleshooting

- If login doesn't work, try running with `--login` flag to force a fresh login
- Delete the `browser_state/` folder to clear saved sessions
- Make sure Playwright browsers are installed with `playwright install`

## Security Note

Your login session is saved locally in the `browser_state/` directory. Keep this secure and don't share these files.