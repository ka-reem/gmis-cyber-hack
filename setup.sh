#!/bin/bash

# GMIS CTF Browser Setup Script
# This script installs Playwright and sets up the browser automation

echo "🚀 Setting up GMIS CTF Browser Automation"
echo "=========================================="

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install

# Make the main script executable
chmod +x ctf_browser.py

echo "✅ Setup complete!"
echo ""
echo "📖 Usage:"
echo "  python ctf_browser.py           # Normal run (uses saved login if available)"
echo "  python ctf_browser.py --login   # Force login (ignore saved state)"
echo ""
echo "🎯 The script will:"
echo "  1. Open the CTF challenges page in a browser"
echo "  2. Save your login state after first login"
echo "  3. Reuse the saved login on subsequent runs"
echo "  4. Keep the browser open until you press Ctrl+C"