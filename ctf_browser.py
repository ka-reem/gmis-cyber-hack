#!/usr/bin/env python3
"""
GMIS CTF Browser Automation with Login State Persistence

This script opens the GMIS CTF challenges page and maintains login session
between runs by saving browser state (cookies, localStorage, etc.).
"""

import asyncio
import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class CTFBrowser:
    def __init__(self):
        self.ctf_url = "https://2025-gmis-advance.ctfd.io/challenges"
        self.state_dir = Path("browser_state")
        self.state_file = self.state_dir / "auth_state.json"
        
        # Create state directory if it doesn't exist
        self.state_dir.mkdir(exist_ok=True)
        
        # Initialize OpenAI client
        self.ai_client = None
        try:
            api_key = os.environ.get("LLAMA_API_KEY")
            if api_key:
                self.ai_client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.llama.com/compat/v1/"
                )
                print(f"[AI] Initialized (key: {api_key[:10]}...)")
            else:
                print("[WARN] LLAMA_API_KEY not found in .env file - AI answering disabled")
                print("[INFO] Create a .env file with: LLAMA_API_KEY=your_key_here")
        except Exception as e:
            print(f"[ERROR] Failed to initialize AI client: {e}")
    
    async def get_ai_answer(self, question_text: str) -> str:
        """Use AI to answer a CTF question"""
        if not self.ai_client:
            return "AI client not initialized"
        
        try:
            print(f"[AI] Asking: {question_text[:100]}...")
            completion = self.ai_client.chat.completions.create(
                model="Llama-4-Maverick-17B-128E-Instruct-FP8",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a CTF (Capture The Flag) expert assistant.

CRITICAL INSTRUCTIONS:
1. Think through the problem step-by-step internally.
2. Pay very close attention to the "Answer Example Format" in the question.
3. Determine whether the candidate answer is directly related to the question.
   - If the answer is NOT clearly related, the model MUST output the single token: NO_ANSWER
4. Output ONLY the final answer in the EXACT format specified by the question (one line only).
5. Do NOT include any explanation, reasoning, or extra text.
6. If the question involves decoding (base64, hex, etc.), perform the decoding and format the decoded value exactly.

Examples:
- If format is "CAHSI-ABCDE12345", answer must be like "CAHSI-ABCDE12345" matching format rules shown.
- If decoding base64 yields "CAHSI-ABCDE12345", output exactly: CAHSI-ABCDE12345

If you cannot produce a related answer, respond exactly with: NO_ANSWER"""
                    },
                    {
                        "role": "user",
                        "content": question_text
                    }
                ],
            )
            answer = completion.choices[0].message.content.strip()
            print(f"[AI] Answer: {answer}")
            return answer
        except Exception as e:
            print(f"[ERROR] AI error: {e}")
            return f"Error: {e}"
    
    async def launch_browser_with_state(self, playwright):
        """Launch browser and load saved state if available"""
        browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=1000,
        )
        
        # Create context with state if it exists
        if self.state_file.exists():
            print("🔄 Loading saved login state...")
            context = await browser.new_context(storage_state=str(self.state_file))
        else:
            print("❗ No saved state found. Please run once with login saved")
            context = await browser.new_context()
        
        return browser, context

    async def extract_question_from_modal(self, page) -> str:
        """Extract question text from the opened modal/dialog"""
        try:
            # Wait a moment for modal to render
            await page.wait_for_timeout(500)
            
            # Try common selectors for question/challenge content
            question_selectors = [
                '.modal-body',
                '[role="dialog"]',
                '.challenge-description',
                '.question',
                '#challenge .description',
                'div.modal-content',
            ]
            
            for selector in question_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible(timeout=1000):
                        text = await element.inner_text()
                        if text and len(text.strip()) > 10:  # Valid question should have some content
                            return text.strip()
                except Exception:
                    continue
            
            # Fallback: get all text from modal/dialog
            try:
                modal = page.locator('[role="dialog"], .modal').first
                if await modal.is_visible(timeout=1000):
                    return await modal.inner_text()
            except Exception:
                pass
            
            return "Could not extract question text"
            
        except Exception as e:
            print(f"⚠️ Error extracting question: {e}")
            return f"Error: {e}"

    async def close_any_modal(self, page, get_question=False):
        """Try a comprehensive list of selectors to close any modal/dialog that opened."""
        close_selectors = [
            # Common close button text
            'button:has-text("×")',
            'button:has-text("✕")',
            'button:has-text("Close")',
            'button:has-text("close")',
            'a:has-text("×")',
            'a:has-text("✕")',
            
            # Common close button classes and attributes
            'button.close',
            'button[class*="close"]',
            'button[aria-label="Close"]',
            'button[aria-label="close"]',
            'button[data-dismiss="modal"]',
            '[data-bs-dismiss="modal"]',
            
            # Modal-specific selectors
            '.modal button.close',
            '.modal .close',
            'div[role="dialog"] button',
            '[role="dialog"] button[class*="close"]',
            
            # XPath fallbacks
            'xpath=//button[contains(text(),"×")]',
            'xpath=//button[contains(text(),"✕")]',
            'xpath=//button[contains(text(),"Close")]',
            'xpath=//button[contains(@class,"close")]',
            'xpath=//button[@aria-label="Close"]',
            'xpath=//div[@role="dialog"]//button',
            'xpath=//*[contains(@class,"modal")]//button[contains(@class,"close")]',
            
            # Generic escape mechanisms
            '.modal-header button',
            '.modal-footer button:last-child',
        ]

        for sel in close_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click(timeout=2000)
                    print(f"🔒 Closed modal using: {sel}")
                    await page.wait_for_timeout(300)
                    return True
            except Exception:
                continue

        # Try ESC key as fallback
        try:
            await page.keyboard.press('Escape')
            print("🔒 Attempted to close modal with ESC key")
            await page.wait_for_timeout(300)
            return True
        except Exception:
            pass

        return False

    async def click_all_challenge_buttons(self, page):
        """Find clickable challenge elements inside <main> and click them one-by-one.

        Strategy:
        - Wait for page to be fully loaded with network idle
        - Try multiple selector strategies to find challenge cards
        - Click each challenge card and close the modal
        """
        print("⏳ Waiting for page to fully load...")
        try:
            await page.wait_for_load_state('networkidle', timeout=10000)  # Reduced from 20s
        except Exception as e:
            print(f"⚠️ Network idle timeout: {e}")
        
        # Wait for dynamic content and any security checks
        print("⏳ Waiting for dynamic content to load...")
        await page.wait_for_timeout(2000)  # Reduced from 5s
        
        print("🔎 Looking for challenge cards using multiple strategies...")
        
        # Strategy 1: Look for divs that might be challenge cards
        strategies = [
            ('div[role="button"]', 'divs with role=button'),
            ('div.challenge-card', 'divs with class challenge-card'),
            ('div.card', 'divs with class card'),
            ('[data-challenge]', 'elements with data-challenge attribute'),
            ('div[onclick]', 'divs with onclick'),
            ('div[class*="challenge"]', 'divs with challenge in class'),
            ('main div:has-text("1")', 'divs containing "1" (point value)'),
        ]
        
        clickable = None
        strategy_used = None
        
        for selector, desc in strategies:
            try:
                loc = page.locator(selector)
                count = await loc.count()
                if count > 0:
                    print(f"✅ Found {count} elements using: {desc} ({selector})")
                    clickable = loc
                    strategy_used = desc
                    break
                else:
                    print(f"❌ No elements found for: {desc}")
            except Exception as e:
                print(f"❌ Error trying {desc}: {e}")
        
        if not clickable:
            print("⚠️ No challenge elements found with any strategy. Trying generic approach...")
            # Fallback: try all clickable elements
            clickable = page.locator('main button, main a, main div[onclick], main div[role="button"]')
        
        total = await clickable.count()
        print(f"🧭 Total elements to click: {total}")
        
        if total == 0:
            print("❌ No clickable elements found. Taking a screenshot for debugging...")
            await page.screenshot(path="debug_screenshot.png")
            print("📸 Screenshot saved to debug_screenshot.png")
            
            # Log page content for debugging
            html = await page.content()
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("📄 Page HTML saved to debug_page.html")
            return

        # Click each element
        for i in range(total):
            try:
                element = clickable.nth(i)
                
                # Check if visible
                if not await element.is_visible():
                    print(f"⏭️ Skipping element #{i} (not visible)")
                    continue

                # Get element info
                text = (await element.inner_text())[:60] if await element.inner_text() else ""
                tag = await element.evaluate("el => el.tagName")
                desc = text.strip() or f'{tag} #{i}'
                
                print(f"➡️ Clicking element #{i+1}/{total}: {desc}")

                # Scroll and click
                await element.scroll_into_view_if_needed()
                await element.click(timeout=5000)

                # Wait for modal to appear
                await page.wait_for_timeout(500)

                # Extract question and get AI answer
                question = await self.extract_question_from_modal(page)
                print(f"📝 Question extracted: {question[:200]}...")
                
                if self.ai_client and question and "Could not extract" not in question:
                    answer = await self.get_ai_answer(question)
                    print(f"💬 AI suggests: {answer}")
                    # TODO: You can add logic here to input the answer if needed
                
                # Try to close modal
                closed = await self.close_any_modal(page, get_question=False)
                if closed:
                    print(f"✅ Closed modal for: {desc}")
                else:
                    print(f"⚠️ No modal found after clicking: {desc}")
                
                # Small delay between clicks
                await page.wait_for_timeout(300)

            except Exception as e:
                print(f"❌ Failed to click element #{i}: {e}")
                continue

        print("✅ Done attempting to click all challenges")

    async def click_elements_by_selector(self, page, selector, delay_ms: int = 0):
        """Click elements matching a provided selector (CSS or XPath)."""
        print(f"🔎 Locating elements by selector: {selector}")
        try:
            elements = page.locator(selector)
            count = await elements.count()
        except Exception as e:
            print(f"❌ Selector error: {e}")
            return
            
        print(f"🧭 Found {count} elements for selector")

        for i in range(count):
            try:
                el = elements.nth(i)
                if not await el.is_visible():
                    continue
                await el.scroll_into_view_if_needed()
                text = (await el.inner_text())[:80] if await el.inner_text() else ""
                desc = text.strip() or (await el.get_attribute('id')) or f'index-{i}'
                print(f"➡️ Clicking selector element #{i}: {desc}")
                await el.click(timeout=5000)
                await page.wait_for_timeout(delay_ms)
                await self.close_any_modal(page)
            except Exception as e:
                print(f"⚠️ Failed to click element #{i}: {e}")

    
    async def run(self):
        """Main execution function"""
        async with async_playwright() as playwright:
            browser, context = await self.launch_browser_with_state(playwright)
            
            try:
                # Create new page
                page = await context.new_page()
                
                print(f"🌐 Navigating to: {self.ctf_url}")
                await page.goto(self.ctf_url)
                
                # Wait for security checks (Cloudflare, etc.)
                print("⏳ Waiting for security checks to complete...")
                await page.wait_for_timeout(2000)  # Initial wait (reduced from 5s)
                
                # Try to detect if security check is present
                security_indicators = [
                    'text="Checking your browser"',
                    'text="Just a moment"',
                    'text="Please wait"',
                    '#challenge-running',
                    '.cf-browser-verification',
                ]
                
                max_security_wait = 15000  # 15 seconds max (reduced from 30s)
                security_wait_start = 0
                
                while security_wait_start < max_security_wait:
                    found_security = False
                    for indicator in security_indicators:
                        try:
                            if await page.locator(indicator).count() > 0:
                                found_security = True
                                print(f"🔒 Security check detected, waiting... ({security_wait_start/1000}s)")
                                break
                        except:
                            pass
                    
                    if not found_security:
                        break
                    
                    await page.wait_for_timeout(1000)  # Check every 1s (reduced from 2s)
                    security_wait_start += 1000
                
                print("✅ Security checks completed (or timed out)")
                
                # Additional wait for page to stabilize
                print("⏳ Waiting for page to stabilize...")
                await page.wait_for_timeout(1000)  # Reduced from 3s
                
                # Determine selector from argv (if provided)
                selector = None
                for i, arg in enumerate(sys.argv):
                    if arg in ("--selector", "-s") and i + 1 < len(sys.argv):
                        selector = sys.argv[i + 1]
                
                # Optional delay between clicks (ms)
                delay_ms = 0
                for i, arg in enumerate(sys.argv):
                    if arg in ("--delay",) and i + 1 < len(sys.argv):
                        try:
                            delay_ms = int(sys.argv[i + 1])
                        except Exception:
                            delay_ms = 0

                # Click elements using selector or default strategy
                if selector:
                    print(f"🔎 Using provided selector: {selector}")
                    if selector.strip().startswith("//") or selector.strip().startswith("xpath="):
                        if not selector.startswith("xpath="):
                            selector = f"xpath={selector}"
                    await self.click_elements_by_selector(page, selector, delay_ms=delay_ms)
                else:
                    await self.click_all_challenge_buttons(page)
                
                print("\n🎯 CTF Challenges page is ready!")
                print("🔄 Your login state has been saved for future runs")
                print("⚡ Next time you run this script, it will use your saved login")
                print("\n💡 Press Ctrl+C to close the browser when done")
                
                # Keep the browser open
                try:
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    print("\n👋 Closing browser...")
                
            except Exception as e:
                print(f"❌ Error: {e}")
            finally:
                await browser.close()


async def main():
    """Main entry point"""
    print("🚀 GMIS CTF Browser Automation")
    print("="*40)
    
    ctf_browser = CTFBrowser()
    await ctf_browser.run()


if __name__ == "__main__":
    asyncio.run(main())