import asyncio
import pyotp
import json
from loguru import logger
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from sdk import config

class UscisClient:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.is_logged_in = False

    async def _init_browser(self):
        if self.playwright:
            return
        self.playwright = await async_playwright().start()
        
        # Use a persistent context to cache login info
        import os
        user_data_dir = os.path.abspath("data/uscis_browser")
        os.makedirs(user_data_dir, exist_ok=True)
        
        logger.info(f"Launching persistent browser context from {user_data_dir}")
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await Stealth().apply_stealth_async(self.page)

    def get_otp(self):
        """Generate OTP code from secret or URI."""
        secret = config.USCIS_TOTP_SECRET
        if not secret:
            logger.error("USCIS_TOTP_SECRET not found in config")
            return "000000"
        if secret.startswith("otpauth://"):
            totp = pyotp.parse_uri(secret)
        else:
            totp = pyotp.TOTP(secret)
        return totp.now()

    async def is_session_active(self):
        """Check if we are already logged in via a fast API probe."""
        try:
            # Try a very fast probe to a real API endpoint
            await self.page.goto("https://my.uscis.gov/account/case-service/api/cases/probe", wait_until="commit", timeout=10000)
            if "sign-in" in self.page.url or "login" in self.page.url:
                return False
            
            # Check if we got a valid JSON with "data" field
            content = await self.page.inner_text("body")
            try:
                data = json.loads(content)
                # If we get that empty error dict, we are not really active
                if data.get("error") is not None and data.get("data") is None:
                    logger.warning("Session probe returned error JSON. Session likely expired.")
                    return False
                self.is_logged_in = True
                return True
            except:
                return False
        except Exception:
            return False

    async def login(self):
        """Complete 2nd-step login process via browser automation."""
        await self._init_browser()
        
        if await self.is_session_active():
            return True

        logger.info(f"Attempting USCIS Browser Login for {config.USCIS_EMAIL}")
        
        try:
            # Start from the applicant page to ensure session return bridge
            logger.info("Navigating to applicant page (which should redirect to sign-in)...")
            try:
                await self.page.goto("https://my.uscis.gov/account/applicant", wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logger.error(f"Navigation failed: {e}")
                await self.page.screenshot(path="logs/uscis_error.png")
                return False
            
            # If not redirected or already there
            if "sign-in" not in self.page.url and "login" not in self.page.url:
                if "/applicant" in self.page.url:
                    logger.info("Already at applicant page.")
                    self.is_logged_in = True
                    return True

            # Wait for email field (which handles the redirect automatically)
            
            # Check for Cloudflare / WAF challenges
            content = await self.page.content()
            if "Verify you are human" in content or "Checking your browser" in content:
                logger.warning("Detected Cloudflare/WAF challenge. Waiting 10s for auto-resolve...")
                await asyncio.sleep(10)
                await self.page.screenshot(path="logs/uscis_waf.png")

            # Wait for email field
            try:
                await self.page.wait_for_selector('input[id*="email"], input[name*="email"]', timeout=15000)
            except:
                logger.error("Email field not found. Logging available selectors.")
                inputs = await self.page.query_selector_all('input')
                for i in inputs:
                    name = await i.get_attribute("name")
                    id_ = await i.get_attribute("id")
                    logger.info(f"Found input: name={name}, id={id_}")
                await self.page.screenshot(path="logs/uscis_login_page_retry.png")
                return False

            # Fill email and password using ID or name
            await self.page.fill('input[id*="email"], input[name*="email"]', config.USCIS_EMAIL)
            await self.page.fill('input[id*="password"], input[name*="password"]', config.USCIS_PASSWORD)
            
            # Submit credentials via Enter key on password field
            logger.info("Submitting credentials via Enter key...")
            await asyncio.sleep(2) 
            await self.page.focus('input[id*="password"], input[name*="password"]')
            await self.page.screenshot(path="logs/uscis_before_enter.png")
            await self.page.press('input[id*="password"], input[name*="password"]', "Enter")
            
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(5) # Wait a bit for potential redirect
            await self.page.screenshot(path="logs/uscis_after_enter.png")

            # Check if we are on the verification page
            try:
                await self.page.wait_for_selector('input[id*="code"], input[name*="code"]', timeout=30000)
            except:
                logger.error(f"Failed to reach verification page. URL: {self.page.url}")
                await self.page.screenshot(path="logs/uscis_otp_missing.png")
                return False

            # Step 2: Verification Code
            otp = self.get_otp()
            logger.info(f"Generated OTP: {otp}. Entering code...")
            await self.page.fill('input[id*="code"], input[name*="code"]', otp)
            
            # Submit OTP
            logger.info("Submitting OTP...")
            await self.page.click('text="Submit"', timeout=15000)
            
            # Can land on /dashboard or /applicant
            try:
                await self.page.wait_for_url(lambda url: "/dashboard" in url or "/applicant" in url, timeout=40000)
                logger.info(f"Target reached: {self.page.url}")
                # Wait for dashboard to load completely as suggested by user
                logger.info("Waiting 5s for dashboard info to load...")
                await asyncio.sleep(5)
                await self.page.screenshot(path="logs/uscis_dashboard.png")
            except Exception as e:
                logger.warning(f"wait_for_url timed out, but continuing... current: {self.page.url}")
                await self.page.screenshot(path="logs/uscis_dashboard_timeout.png")

            logger.info("USCIS Browser Login Successful")
            self.is_logged_in = True
            return True

        except Exception as e:
            logger.error(f"USCIS Browser Login Failed: {e}")
            await self.page.screenshot(path="logs/uscis_fatal_error.png")
            return False

    async def bridge_session(self):
        """Navigate to applicant page and wait for session to stabilize."""
        bridge_url = "https://my.uscis.gov/account/applicant"
        logger.info("Bridging session: Navigating to applicant page and waiting...")
        await self.page.goto(bridge_url, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(8) # Wait for background session sync
        await self.page.screenshot(path="logs/uscis_bridged.png")

    async def get_case_status(self, case_number):
        """Fetch status by directly navigating to the API URL in the browser."""
        if not self.is_logged_in:
            if not await self.login():
                return {"error": "Authentication failed"}

        try:
            url = f"https://my.uscis.gov/account/case-service/api/cases/{case_number}"
            logger.info(f"Directly navigating to API: {url}")
            
            # Simple direct navigation. Browser handles cookies/session automatically.
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Retrieve the full body text (the JSON)
            content = await self.page.inner_text("body")
            
            try:
                result_json = json.loads(content)
                logger.debug(f"Captured JSON for {case_number}: {result_json}")
                return result_json
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON for {case_number}. Content starts with: {content[:100]}")
                return {"error": "Invalid JSON response", "content": content[:500]}

        except Exception as e:
            logger.error(f"Failed to fetch status for {case_number}: {e}")
            return {"error": str(e)}

    async def check_all(self, case_list: list = None):
        """Check specified cases (or all configured ones) with fail-fast logic."""
        if not self.is_logged_in:
            if not await self.login():
                 return {}

        target_cases = case_list or config.USCIS_CASE_NUMBERS
        results = {}
        for idx, cn in enumerate(target_cases):
            logger.info(f"Checking USCIS Case: {cn}")
            status = await self.get_case_status(cn)
            results[cn] = status
            
            # Log error but continue to next case
            if isinstance(status, dict) and status.get("error") is not None:
                logger.error(f"Error fetching {cn}: {status['error']}")
                
            # Only sleep if there are more cases to check
            if idx < len(target_cases) - 1:
                await asyncio.sleep(2) 
        return results

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

async def get_formatted_report(case_list: list = None, show_diff: bool = True) -> str:
    """
    Fetches USCIS status, optionally compares with saved state, and returns a formatted Markdown report.
    Args:
        case_list: List of case numbers to check. Defaults to all configured in config.
        show_diff: Whether to load previous state and show differences.
    """
    import os
    from sdk.uscis import UscisClient
    
    state_file = "data/uscis_state.json"
    client = UscisClient()
    try:
        # Fetch status for the requested list
        results = await client.check_all(case_list=case_list)

        # Always try to load existing state (both for diffing and merging)
        old_statuses = {}
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    old_statuses = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state file: {e}")

        is_multiple = len(results) > 1
        report = "📋 <b>USCIS Case Status Report</b>\n\n" if is_multiple else ""
        
        # We will merge new results into the global state
        new_state = old_statuses.copy()

        for cn, status in results.items():
            if not status or status.get("error") is not None:
                error_obj = status.get("error") if status else "Unknown error"
                # Handle dictionary error messages from API
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get("userMessage") or "Session Expired or API Error"
                    if not error_obj.get("userMessage") and error_obj.get("requestId"):
                        error_msg += f" (Req: {error_obj['requestId'][:8]})"
                else:
                    error_msg = str(error_obj)

                report += f"❌ <code>{cn}</code>: {error_msg}\n"
                continue

            # Update merged state only on success
            new_state[cn] = status

            # Extract data
            data = status.get("data")
            if not data:
                report += f"⚠️ <code>{cn}</code>: No data returned\n"
                continue
                
            form_type = data.get("formType", "N/A")
            form_name = data.get("formName", "Unknown")
            updated_at = data.get("updatedAtTimestamp", "Unknown")
            
            # Extract event codes
            events = data.get("events", [])
            event_codes = [e.get("eventCode", "?") for e in events]
            event_str = ", ".join(event_codes) if event_codes else "None"
            
            if is_multiple:
                report += f"🔹 <tg-spoiler>{cn}</tg-spoiler> ({form_type})\n   {form_name}\n"
            else:
                report += (
                    f"🇺🇸 <b>USCIS Case Status</b>\n\n"
                    f"<b>Case #:</b> <tg-spoiler>{cn}</tg-spoiler>\n"
                    f"<b>Form:</b> {form_type}\n"
                    f"<b>Type:</b> {form_name}\n"
                )

            report += f"   📋 Events: <code>{event_str}</code>\n"
            report += f"   Last updated: <code>{updated_at}</code>\n"
            
            # Diff logic
            if show_diff:
                old_data = old_statuses.get(cn, {}).get("data") if old_statuses.get(cn) else None
                changes = []
                if old_data:
                    old_updated_at = old_data.get("updatedAtTimestamp", "")
                    if old_updated_at and old_updated_at != updated_at:
                        changes.append(f"📅 <code>{old_updated_at}</code> → <code>{updated_at}</code>")
                        
                        on = len(old_data.get("notices", []))
                        nn = len(data.get("notices", []))
                        if nn > on: changes.append(f"📬 New notices: +{nn-on}")
                        
                        oe = len(old_data.get("events", []))
                        ne = len(data.get("events", []))
                        if ne > oe: changes.append(f"📋 New events: +{ne-oe}")
                    
                    if changes:
                        report += f"   📊 <b>Changes:</b>\n   " + "\n   ".join(changes) + "\n"
                    else:
                        report += "   ✅ No changes since last check\n"
                else:
                    report += "   🆕 First time checking this case\n"
            
            report += "\n"
        
        # Save the merged state back to disk
        try:
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            with open(state_file, 'w') as f:
                json.dump(new_state, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved merged USCIS state to {state_file}")
        except Exception as e:
            logger.error(f"Failed to save USCIS state: {e}")

        return report.strip()
    except Exception as e:
        logger.error(f"Failed to generate USCIS report: {e}")
        return f"❌ Error generating report: {str(e)}"
    finally:
        await client.close()
