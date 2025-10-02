# CTF Browser Automation - Usage Guide

## Quick Start

```bash
# Activate virtual environment
source venv/bin/activate

# Run the script
python ctf_browser.py
```

## What the Script Does

1. ✅ Loads saved login session from `browser_state/auth_state.json`
2. 🌐 Navigates to CTF challenges page
3. ⏳ Waits for security checks (Cloudflare, etc.) - up to 30 seconds
4. 🔎 Automatically finds and clicks all challenge cards
5. ❌ Closes modals after each click using ESC or close buttons
6. 🖥️ Keeps browser open until you press Ctrl+C

## Command Line Options

### Basic Usage
```bash
python ctf_browser.py
```
Uses automatic detection to find and click all challenge cards.

### Use Custom Selector
```bash
python ctf_browser.py --selector 'div.challenge-card'
python ctf_browser.py -s 'button:has-text("View")'
```
Click only elements matching the specified CSS selector.

### Add Delay Between Clicks
```bash
python ctf_browser.py --delay 1000
```
Waits 1000ms (1 second) between each click.

### Combine Options
```bash
python ctf_browser.py --selector 'div.card' --delay 500
```

## Detection Strategies

The script automatically tries multiple strategies to find challenge cards:

1. `div[role="button"]` - Divs with role=button
2. `div.challenge-card` - Divs with class challenge-card
3. `div.card` - Divs with class card
4. `[data-challenge]` - Elements with data-challenge attribute
5. `div[onclick]` - Divs with onclick handlers
6. `div[class*="challenge"]` - Divs with "challenge" in class name
7. `main div:has-text("1")` - Divs containing "1" (point values)

## Modal Closing

After each click, the script tries to close modals using:
- Close button text (×, ✕, Close)
- Common close button classes
- Modal-specific selectors
- ESC key as fallback

## Debugging

If no elements are found, the script automatically:
- 📸 Takes a screenshot → `debug_screenshot.png`
- 📄 Saves page HTML → `debug_page.html`

Send these files to debug selector issues.

## Files Created

- `browser_state/auth_state.json` - Your saved login session
- `debug_screenshot.png` - Screenshot when no elements found
- `debug_page.html` - Full page HTML for debugging

## Security

- Login session is saved locally in `browser_state/`
- Keep this directory secure
- Don't share `auth_state.json`

## Tips

- First run: Log in manually, the state will be saved automatically
- Subsequent runs: State is loaded automatically
- If login expires: Delete `browser_state/` and log in again
- Press Ctrl+C to close the browser when done
