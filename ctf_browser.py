#!/usr/bin/env python3
"""
GMIS CTF Browser Automation with Login State Persistence

This script opens the GMIS CTF challenges page and maintains login session
between runs by saving browser state (cookies, localStorage, etc.).
"""

import asyncio
import os
import sys
import re
from pathlib import Path
from playwright.async_api import async_playwright


class CTFBrowser:
    def __init__(self):
        self.ctf_url = "https://2025-gmis-advance.ctfd.io/challenges"
        self.state_dir = Path("browser_state")
        self.state_file = self.state_dir / "auth_state.json"
        
        # Create state directory if it doesn't exist
        self.state_dir.mkdir(exist_ok=True)
    
    async def launch_browser_with_state(self, playwright):
        """Launch browser and load saved state if available"""
        # Launch browser with persistent context for better state management
        browser = await playwright.chromium.launch(
            headless=False,  # Set to True if you want headless mode
            slow_mo=1000,    # Slow down operations for better visibility
        )
        
        # Create context with state if it exists
        if self.state_file.exists():
            print("🔄 Loading saved login state...")
            context = await browser.new_context(storage_state=str(self.state_file))
        else:
            print("❗ No saved state found. Please run once with login saved (this script expects saved state)")
            context = await browser.new_context()
        
        return browser, context
    
    async def save_login_state(self, context):
        """Save current browser state for future use"""
        try:
            await context.storage_state(path=str(self.state_file))
            print("✅ Login state saved successfully!")
        except Exception as e:
            print(f"❌ Failed to save login state: {e}")
    
    async def check_if_logged_in(self, page):
        """Check if user is already logged in"""
        try:
            # Wait a bit for the page to load
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Check for common login indicators
            # This might need adjustment based on the actual CTF site structure
            login_indicators = [
                'text="Login"',
                'text="Sign In"', 
                'input[name="username"]',
                'input[name="password"]',
                'button[type="submit"]'
            ]
            
            for indicator in login_indicators:
                try:
                    element = await page.wait_for_selector(indicator, timeout=2000)
                    if element:
                        return False  # Login form found, not logged in
                except:
                    continue
            
            # If no login form found, assume logged in
            return True
            
        except Exception as e:
            print(f"⚠️ Could not determine login status: {e}")
            return False
    
    async def prompt_for_login(self, page):
        """Prompt user to complete login manually"""
        print("\n" + "="*50)
        print("🔐 PLEASE COMPLETE LOGIN MANUALLY")
        print("="*50)
        print("1. The browser window should be open")
        print("2. Please log in to the CTF platform")
        print("3. Navigate to the challenges page if not there already")
        print("4. Press ENTER here when login is complete...")
        print("="*50)
        
        # Wait for user to complete login
        input("Press ENTER when you've completed login: ")
        
        # Save the state after manual login
        print("💾 Saving login state...")
        return True

    async def close_any_modal(self, page):
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
            await page.wait_for_load_state('networkidle', timeout=20000)  # Increased to 20s
        except Exception as e:
            print(f"⚠️ Network idle timeout: {e}")
        
        # Wait longer for dynamic content and any security checks
        print("⏳ Waiting for dynamic content to load...")
        await page.wait_for_timeout(5000)  # Increased to 5s
        
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
                await page.wait_for_timeout(1000)

                # Try to close modal
                closed = await self.close_any_modal(page)
                if closed:
                    print(f"✅ Closed modal for: {desc}")
                else:
                    print(f"⚠️ No modal found after clicking: {desc}")
                
                # Small delay between clicks
                await page.wait_for_timeout(500)

            except Exception as e:
                print(f"❌ Failed to click element #{i}: {e}")
                continue

        print("✅ Done attempting to click all challenges")

    async def click_elements_by_selector(self, page, selector, delay_ms: int = 0):
        """Click elements matching a provided selector (CSS or Playwright XPath)."""
        print(f"🔎 Locating elements by selector: {selector}")
        try:
            elements = page.locator(selector)
            count = await elements.count()
        except Exception as e:
            text = str(e)
            print(f"❌ Error: {text}")
            # If the error looks like an invalid XPath, try a CSS fallback
            if 'not a valid XPath' in text or "Failed to execute 'evaluate' on 'Document'" in text or 'SyntaxError' in text:
                # convert simple xpath to css and retry
                xpath = selector
                if xpath.startswith('xpath='):
                    xpath = xpath[len('xpath='):]
                css_candidate = self._simple_xpath_to_css(xpath)
                if css_candidate:
                    print(f"🔁 Retrying with CSS fallback: {css_candidate}")
                    elements = page.locator(css_candidate)
                    count = await elements.count()
                else:
                    print("⚠️ Could not convert XPath to CSS fallback.")
                    return
            else:
                print(f"⚠️ Selector error: {e}")
                return
        print(f"🧭 Found {count} elements for selector")

        for i in range(count):
            try:
                el = elements.nth(i)
                if not await el.is_visible():
                    continue
                await el.scroll_into_view_if_needed()
                text = (await el.inner_text())[:80]
                desc = text.strip() or (await el.get_attribute('id')) or (await el.get_attribute('class')) or f'index-{i}'
                print(f"➡️ Clicking selector element #{i}: {desc}")
                await el.click(timeout=5000)
                await page.wait_for_timeout(delay_ms)
                # attempt to close modal if any
                await self.close_any_modal(page)
            except Exception as e:
                print(f"⚠️ Failed to click element #{i} for selector {selector}: {e}")

    async def probe_selectors(self, page, candidates: list[str], out_path: str = "selector_probe_log.json"):
        """Try a list of candidate selectors and log whether they locate elements or can be clicked.

        Writes a JSON file with entries: {selector, found_count, clickable_count, error}
        """
        import json

        results = []
        for sel in candidates:
            record = {"selector": sel, "found_count": 0, "clickable_count": 0, "error": None}
            try:
                # Normalize xpath if necessary
                s = sel
                if s.strip().startswith('//'):
                    s = f"xpath={s}"

                loc = page.locator(s)
                try:
                    cnt = await loc.count()
                except Exception as e:
                    record["error"] = str(e)
                    results.append(record)
                    print(f"❌ Probe {sel}: error during count: {e}")
                    continue

                record["found_count"] = cnt
                clickable = 0
                for i in range(cnt):
                    try:
                        el = loc.nth(i)
                        if not await el.is_visible():
                            continue
                        clickable += 1
                    except Exception:
                        continue
                record["clickable_count"] = clickable
                print(f"🔎 Probe {sel}: found={cnt}, visible_clickable={clickable}")
            except Exception as e:
                record["error"] = str(e)
            results.append(record)

        # write results
        try:
            with open(out_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"📁 Probe results written to {out_path}")
        except Exception as e:
            print(f"❌ Failed to write probe log: {e}")

    async def deep_probe(self, page, out_path: str = "deep_probe_log.json", max_elements: int = 300):
        """Collect detailed info for elements under <main> and write to JSON for inspection.

        This includes tagName, id, className, role, text snippet, attributes, an outerHTML snippet
        and a generated CSS path (best-effort). Useful for crafting precise selectors.
        """
        import json

        print("🔬 Running deep probe of <main> elements...")
        # Wait for main or fallback to body
        try:
            await page.wait_for_selector('main', timeout=5000)
            root_selector = 'main'
        except Exception:
            root_selector = 'body'

        script = f"""
        (rootSel, maxEls) => {{
            function cssPath(el) {{
                if (!el) return null;
                var parts = [];
                while (el && el.nodeType === Node.ELEMENT_NODE && el.tagName.toLowerCase() !== 'html') {{
                    var part = el.tagName.toLowerCase();
                    if (el.id) {{ part += '#' + el.id; parts.unshift(part); break; }}
                    if (el.className) {{
                        var cls = el.className.trim().split(/\s+/)[0];
                        if (cls) part += '.' + cls;
                    }}
                    var parent = el.parentNode;
                    if (!parent) {{ parts.unshift(part); break; }}
                    var siblings = Array.from(parent.children).filter(e => e.tagName === el.tagName);
                    if (siblings.length > 1) {{
                        var ix = Array.from(parent.children).indexOf(el) + 1;
                        part += ':nth-child(' + ix + ')';
                    }}
                    parts.unshift(part);
                    el = parent;
                }}
                return parts.join(' > ');
            }}

            var root = document.querySelector(rootSel) || document.body;
            var all = Array.from(root.querySelectorAll('*'));
            var out = [];
            for (var i=0;i<Math.min(all.length, maxEls);i++) {{
                var e = all[i];
                var attrs = {{}};
                for (var j=0;j<e.attributes.length;j++) {{ attrs[e.attributes[j].name] = e.attributes[j].value; }}
                out.push({{
                    tag: e.tagName.toLowerCase(),
                    id: e.id || null,
                    class: e.className || null,
                    role: e.getAttribute('role') || null,
                    text: (e.innerText || '').trim().slice(0,200),
                    outerHTML_snippet: (e.outerHTML || '').slice(0,500),
                    attributes: attrs,
                    cssPath: cssPath(e)
                }});
            }}
            return {{root: rootSel, total: all.length, sampled: out.length, items: out}};
        }}
        """

        try:
            data = await page.evaluate(script, root_selector, max_elements)
            # write to file
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"📁 Deep probe written to {out_path} (sampled {data.get('sampled')} of {data.get('total')})")
        except Exception as e:
            print(f"❌ Deep probe failed: {e}")

    def _simple_xpath_to_css(self, xpath: str) -> str | None:
        """A very small XPath -> CSS converter for commonly-used simple patterns.

        Examples handled:
        - //div[@id="challenge"]//a/small  -> div#challenge a small  -> #challenge a small
        - //tag[@id='x']//child -> #x child

        This is intentionally limited and heuristic; for complex XPath use a correct CSS selector manually.
        """
        try:
            s = xpath.strip()
            # remove leading // or /
            s = re.sub(r'^//?', '', s)
            # collapse // to space (descendant) and / to space (child)
            s = s.replace('//', ' ').replace('/', ' ')
            # convert tag[@id="foo"] -> tag#foo
            s = re.sub(r"([a-zA-Z0-9_-]*)\[@id=[\"']([^\"']+)[\"']\]", lambda m: (m.group(1) or '') + ('#' + m.group(2)), s)
            # remove other predicates like [1] or [contains(...)]
            s = re.sub(r'\[.*?\]', '', s)
            # remove empty tag names at start
            parts = [p for p in s.split() if p and p != '*']
            if not parts:
                return None
            css = ' '.join(parts)
            # If starts with tag#id, simplify to just #id
            css = re.sub(r'^([a-zA-Z0-9_-]+)#', lambda m: '#' + m.group(0).split('#', 1)[1] if m else m.group(0), css)
            return css
        except Exception:
            return None

    
    async def run(self, force_login=False):
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
                await page.wait_for_timeout(5000)  # Initial wait
                
                # Try to detect if security check is present
                security_indicators = [
                    'text="Checking your browser"',
                    'text="Just a moment"',
                    'text="Please wait"',
                    '#challenge-running',
                    '.cf-browser-verification',
                ]
                
                max_security_wait = 30000  # 30 seconds max
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
                    
                    await page.wait_for_timeout(2000)
                    security_wait_start += 2000
                
                print("✅ Security checks completed (or timed out)")
                
                # Additional wait for page to stabilize
                print("⏳ Waiting for page to stabilize...")
                await page.wait_for_timeout(3000)
                
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

                deep_probe_mode = '--deep-probe' in sys.argv

                # If --probe present in argv, run selector probing and exit
                probe_mode = '--probe' in sys.argv
                # If selector provided, click only those; else click all inside main
                if selector:
                    print(f"🔎 Using provided selector: {selector}")
                    # detect xpath vs css
                    if selector.strip().startswith("//") or selector.strip().startswith("xpath="):
                        # normalize xpath to Playwright xpath syntax
                        if not selector.startswith("xpath="):
                            selector = f"xpath={selector}"
                    await self.click_elements_by_selector(page, selector, delay_ms=delay_ms)
                else:
                    if probe_mode:
                        # default candidate selectors to test
                        candidates = [
                            '//div[@id="challenge"]//a/small',
                            'div#challenge a small',
                            'main button',
                            'main a',
                            'div.challenge a',
                            'div.challenge button',
                            'button:has-text("Open")',
                            'button:has-text("Details")',
                            'xpath=//button[contains(@class, "challenge")]',
                        ]
                        await self.probe_selectors(page, candidates)
                    elif deep_probe_mode:
                        await self.deep_probe(page)
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
    # Check for command line arguments
    force_login = "--login" in sys.argv or "--force-login" in sys.argv
    
    print("🚀 GMIS CTF Browser Automation")
    print("="*40)
    
    if force_login:
        print("🔄 Force login mode enabled")
    
    ctf_browser = CTFBrowser()
    await ctf_browser.run(force_login=force_login)


if __name__ == "__main__":
    asyncio.run(main())