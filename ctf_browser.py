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
from dotenv import load_dotenv
from openai import OpenAI
import re
from collections import Counter
import math
import base64

# Default index to start clicking from (0-based). Change this value to start anywhere.
DEFAULT_START_INDEX = 58

# Load environment variables from .env file (kept for compatibility)
load_dotenv()


class CTFBrowser:
    def __init__(self):
        self.ctf_url = "https://2025-gmis-advance.ctfd.io/challenges"
        self.state_dir = Path("browser_state")
        self.state_file = self.state_dir / "auth_state.json"
        
        # Create state directory if it doesn't exist
        self.state_dir.mkdir(exist_ok=True)
        
        # Initialize optional LLM client (used only for validation/suggestions)
        self.llm_client = None
        try:
            api_key = os.environ.get("LLAMA_API_KEY")
            if api_key:
                self.llm_client = OpenAI(api_key=api_key, base_url="https://api.llama.com/compat/v1/")
                print(f"[AI] LLM initialized")
            else:
                print("[INFO] LLAMA_API_KEY not set — LLM validation disabled")
        except Exception as e:
            print(f"[WARN] Failed to init LLM client: {e}")
    
    # ---- Decoding-based helpers (replace LLM flow) ----
    def extract_encoded_token(self, text: str):
        """Extract the base64 token from question text.
        
        Expected pattern: "message: <TOKEN>" where TOKEN is the encoded string
        and TOKEN ends at newline or "Answer Example Format".
        """
        if not text:
            return None
        
        # Look for pattern: "message:" followed by base64-like token
        # Token is alphanumeric+/+ with optional = padding
        m = re.search(r'message:\s*([A-Za-z0-9+/]+=*)', text, re.IGNORECASE)
        if m:
            token = m.group(1).strip()
            # Clean up: remove trailing non-base64 chars if any
            token = re.sub(r'[^A-Za-z0-9+/=]+$', '', token)
            return token
        
        return None

    def try_base64_decode(self, s: str):
        """Try to base64-decode s and return decoded str on success or None."""
        try:
            decoded_bytes = base64.b64decode(s, validate=True)
            decoded = decoded_bytes.decode('utf-8')
            return decoded
        except Exception:
            return None

    def llm_is_word(self, candidate: str) -> bool:
        """Ask the LLM whether candidate is a single English word. Returns True if yes."""
        if not self.llm_client or not candidate:
            return False
        try:
            prompt = (
                "You are a terse assistant. Reply with exactly one token: YES if the following"
                " string is a valid English word, or NO otherwise. Do NOT add any explanation.\n\n"
                f"String: {candidate}\n"
            )
            resp = self.llm_client.chat.completions.create(
                model="Llama-4-Maverick-17B-128E-Instruct-FP8",
                messages=[
                    {"role": "system", "content": "You must reply with exactly YES or NO, nothing else."},
                    {"role": "user", "content": prompt}
                ],
            )
            out_raw = resp.choices[0].message.content.strip()
            out = out_raw.splitlines()[0].strip().upper()
            # Accept only exact YES
            return out == 'YES'
        except Exception:
            return False

    def llm_suggest_candidate(self, original_encoded: str) -> str:
        """Ask the LLM to attempt alternative decodings/transforms on the original encoded token and
        return a single candidate token (single line) that looks like an English word, or NO_CANDIDATE.
        """
        if not self.llm_client or not original_encoded:
            return 'NO_CANDIDATE'
        try:
            system = "You are an assistant that suggests a single candidate English word by trying common decodings (base64, hex, rot13, URL, etc.) from a provided encoded token. Reply with one token (the candidate) or NO_CANDIDATE."
            user = (
                f"Original encoded token: {original_encoded}\n\n"
                "Try common decoding/transformation strategies and return the single best candidate word you find, or NO_CANDIDATE if none."
            )
            resp = self.llm_client.chat.completions.create(
                model="Llama-4-Maverick-17B-128E-Instruct-FP8",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=64,
            )
            raw = resp.choices[0].message.content.strip()
            # Log raw response for debugging
            print(f"[AI] raw suggestion: {raw}")
            if not raw:
                return 'NO_CANDIDATE'
            # Extract a single token-like candidate (letters/digits/_/-) with length >=4
            m = re.search(r'([A-Za-z0-9_-]{4,})', raw)
            if m:
                return m.group(1)
            return 'NO_CANDIDATE'
        except Exception:
            return 'NO_CANDIDATE'

    def decode_try_double(self, s: str):
        """Attempt single decode; if it fails or result looks still encoded, try decode again."""
        first = self.try_base64_decode(s)
        if first:
            # If first decode looks readable (contains spaces or letters), return it
            if re.search(r"[A-Za-z0-9\s\-_,.:;@()]+", first):
                return first
            # Otherwise, perhaps it's still base64: try decode again
            second = self.try_base64_decode(first)
            if second:
                return second
            return first

        # If single decode failed, try decode after stripping padding or trying common transforms
        try_variants = [s.strip(), s.replace('\n', ''), s.rstrip('=') + '==']
        for v in try_variants:
            d = self.try_base64_decode(v)
            if d:
                return d

        return None
    
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

    def is_flag_like_question(self, text: str) -> bool:
        """Heuristic: return True if the question looks like a decoding/flag-format task."""
        if not text:
            return False
        t = text.lower()
        keywords = [
            'decode', 'decoding', 'base64', 'hex', 'rot13', 'flag', 'cipher', 'ciphertext',
            'answer example', 'example format', 'flag format', 'encoded'
        ]
        for k in keywords:
            if k in t:
                return True
        # also consider short indicator patterns like strings with lots of equals (base64)
        if re.search(r"[A-Za-z0-9+/]{8,}={0,2}", text):
            return True
        return False

    def extract_required_prefix_from_question(self, text: str):
        """Try to extract a required prefix (like 'CAHSI-') from the question text.

        Returns the prefix including the trailing hyphen (e.g. 'CAHSI-') or None.
        """
        if not text:
            return None

        # Look for explicit 'Answer Example Format' lines
        m = re.search(r'Answer Example Format\s*[:\-]?\s*([A-Za-z0-9\-_]+-[A-Za-z0-9\-_]+)', text, re.IGNORECASE)
        if m:
            s = m.group(1)
            if '-' in s:
                return s.split('-')[0] + '-'
            return s

        # Prefer explicit CAHSI- prefix when present
        m2 = re.search(r'\b(CAHSI-)', text)
        if m2:
            return m2.group(1)

        # Generic uppercase prefix followed by hyphen
        m3 = re.search(r'\b([A-Z]{2,10}-)', text)
        if m3:
            return m3.group(1)

        return None

    async def decode_and_submit_from_question(self, page, question: str):
        """Extract encoded token from question, decode in a loop until LLM validates it as a word, then submit.

        Returns True if a submission was performed, False otherwise.
        """
        encoded_token = self.extract_encoded_token(question)
        if not encoded_token:
            print('[SKIP] No encoded token found in question (expected after "message:")')
            return False

        print(f'[INFO] Extracted encoded token: {encoded_token[:80]}...')
        
        # Decode in a loop until the result starts with "CAHSI"
        current = encoded_token
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            print(f'[INFO] Decode iteration {iteration}: attempting base64 decode...')
            
            decoded = self.try_base64_decode(current)
            if not decoded:
                print(f'[SKIP] Base64 decode failed at iteration {iteration}')
                return False
            
            decoded = decoded.strip()
            print(f'[INFO] Decoded to: {decoded[:100]}')
            
            # Check if decoded string starts with "CAHSI"
            if decoded.startswith('CAHSI'):
                print(f'[ACTION] Found CAHSI prefix after {iteration} iterations!')
                candidate = decoded
                break
            else:
                # Not starting with CAHSI yet, decode again
                print(f'[INFO] Does not start with CAHSI yet; will decode again')
                current = decoded
        else:
            # Loop exhausted without finding CAHSI prefix
            print(f'[SKIP] Reached max iterations ({max_iterations}) without finding CAHSI prefix')
            return False
        
        # Validate candidate before submission
        if not re.search(r'[A-Za-z0-9]', candidate):
            print('[SKIP] Final candidate is empty or non-alphanumeric')
            return False
        
        # Submit the decoded value AS-IS (already has CAHSI- prefix)
        final = candidate
        print(f'[ACTION] Final decoded payload for submission: {final}')
        submitted = await self.submit_answer(page, final)
        if submitted:
            print(f'[ACTION] Submitted decoded flag: {final}')
            return True
        else:
            print('[WARN] Submission failed')
            return False

    async def submit_answer(self, page, answer: str) -> bool:
        """Attempt to fill and submit an answer inside the currently open modal.

        Returns True if it appears we submitted something, False otherwise.
        """
        try:
            # Common selectors for inputs inside modals
            input_selectors = [
                'input[type="text"]',
                'input[name="submission"]',
                'input[name="answer"]',
                'textarea',
                'input[placeholder*="flag"]',
                'input[placeholder*="answer"]',
                'textarea[placeholder*="flag"]',
                'input[class*="answer"]',
                'xpath=//input',
                'xpath=//textarea',
            ]

            # Prefer inputs inside the modal/dialog context
            containers = [
                page.locator('#challenge').first,
                page.locator('[role="dialog"]').first,
                page.locator('.modal').first,
            ]

            # Build list of visible containers (async checks)
            use_containers = []
            for c in containers:
                try:
                    cnt = await c.count()
                    if cnt and await c.is_visible(timeout=200):
                        use_containers.append(c)
                except Exception:
                    continue

            # If no visible container, fall back to whole page
            if not use_containers:
                use_containers = [page]

            for sel in input_selectors:
                for container in use_containers:
                    try:
                        el = container.locator(sel).first
                        # Some locators may not exist; check count
                        if await el.count() == 0:
                            continue
                        if not await el.is_visible(timeout=500):
                            continue

                        print(f"[DEBUG] Filling selector {sel} inside container with: {answer}")
                        await el.fill(answer)

                        # Verify value was set
                        try:
                            current = await el.input_value()
                        except Exception:
                            current = None

                        if current is None or current.strip() == '':
                            print(f"[WARN] After fill, input value is empty for selector {sel} (got: {current})")
                            continue

                        # Try to find a submit button inside the same container first
                        submit_btn = container.locator('button:has-text("Submit"), button:has-text("submit"), button[type="submit"], button:has-text("Answer")').first
                        if await submit_btn.count() and await submit_btn.is_visible(timeout=500):
                            await submit_btn.click()
                            await page.wait_for_timeout(500)
                            print(f"[ACTION] Submitted answer using button for selector {sel}")
                            return True

                        # Otherwise press Enter in the input (ensure focus)
                        try:
                            await el.focus()
                            await el.press('Enter')
                            await page.wait_for_timeout(500)
                            print(f"[ACTION] Submitted answer by pressing Enter in field {sel}")
                            return True
                        except Exception as e:
                            print(f"[WARN] Could not submit by Enter for {sel}: {e}")
                            continue

                    except Exception as e:
                        # continue to next container/selector
                        # print debug for visibility
                        # print(f"[DEBUG] selector {sel} in container error: {e}")
                        continue

            print('[WARN] No input/submit button found inside modal to submit answer')
            return False

        except Exception as e:
            print(f"[ERROR] submit_answer error: {e}")
            return False

    def is_answer_related(self, question: str, answer: str) -> bool:
        """Lightweight relatedness heuristic:

        - Tokenize question and answer, remove short stopwords
        - If there is token overlap above a small threshold, consider related
        - If question contains explicit decoding keywords, prefer that answer decodes to expected pattern via prefix checks
        - Return False for trivial mismatches (empty, NO_ANSWER, Error)
        """
        if not question or not answer:
            return False
        a = answer.strip()
        if a in ('NO_ANSWER', ''):
            return False

        # Normalize and tokenize
        def tokenize(s):
            s = s.lower()
            s = re.sub(r"[^a-z0-9\-\s]", ' ', s)
            tokens = [t for t in s.split() if len(t) > 2]
            return tokens

        q_tokens = tokenize(question)
        a_tokens = tokenize(a)
        if not q_tokens or not a_tokens:
            return False

        q_counts = Counter(q_tokens)
        a_counts = Counter(a_tokens)

        # Count overlap
        overlap = sum((q_counts & a_counts).values())
        overlap_score = overlap / max(1, len(q_tokens))

        # If overlap is at least 20% of question tokens, accept
        if overlap_score >= 0.20:
            return True

        # If question looks like decoding and answer contains uncommon flag-like token, accept
        if self.is_flag_like_question(question):
            # flag-like: contains uppercase-hyphen or common flag prefix
            if re.search(r"[A-Z]{2,10}-[A-Za-z0-9_-]{4,}", a):
                return True

        # If a long substring of answer appears in question (or vice versa), accept
        if len(a) > 6 and a.lower() in question.lower():
            return True

        # otherwise reject
        return False

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
        # Start index support: use self.start_index if set, else DEFAULT_START_INDEX
        start_index = getattr(self, 'start_index', None)
        if start_index is None:
            start_index = DEFAULT_START_INDEX

        for i in range(start_index, total):
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

                # Extract question and decide whether to ask AI
                question = await self.extract_question_from_modal(page)
                print(f"[INFO] Question extracted: {question[:200]}...")

                # Decide if this looks like a decoding/flag question
                if not self.is_flag_like_question(question):
                    print("[SKIP] Not a flag/decoding question — skim")
                else:
                    # Try to find required prefix (e.g., CAHSI-)
                    prefix = self.extract_required_prefix_from_question(question)
                    if prefix:
                        print(f"[INFO] Detected required prefix: {prefix}")

                    # Use decoding-based approach instead of LLM
                    did_submit = await self.decode_and_submit_from_question(page, question)
                    if not did_submit:
                        print('[SKIP] No decoded submission made')
                
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

        # Start index support: use self.start_index if set, else DEFAULT_START_INDEX
        start_index = getattr(self, 'start_index', None)
        if start_index is None:
            start_index = DEFAULT_START_INDEX
        for i in range(start_index, count):
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

                # Optional start index (0-based) via CLI. If not provided, leave
                # self.start_index as None so DEFAULT_START_INDEX (the constant)
                # is used by the click helpers.
                start_index_cli = None
                for i, arg in enumerate(sys.argv):
                    if arg in ("--start", "--index") and i + 1 < len(sys.argv):
                        try:
                            start_index_cli = int(sys.argv[i + 1])
                        except Exception:
                            start_index_cli = 0

                # Only set attribute if CLI provided a value; otherwise keep it None
                self.start_index = (max(0, start_index_cli)
                                    if start_index_cli is not None else None)

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