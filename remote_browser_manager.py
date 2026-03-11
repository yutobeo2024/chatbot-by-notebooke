import os
import subprocess
import time
import signal
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

class RemoteBrowserManager:
    def __init__(self, port_vnc=5901, port_web=6081):
        self.port_vnc = port_vnc
        self.port_web = port_web
        self.xvfb_proc = None
        self.vnc_proc = None
        self.novnc_proc = None
        self.browser_proc = None
        self.display = ":99"
        self.user_data_dir = "/tmp/notebooklm-remote-profile"

    def _find_binary(self, name):
        """Finds a binary on the system."""
        path = shutil.which(name)
        if path:
            return path
        # Common fallback paths for Ubuntu/Debian
        fallbacks = [f"/usr/bin/{name}", f"/usr/local/bin/{name}", f"/usr/bin/{name.lower()}"]
        for f in fallbacks:
            if os.path.exists(f):
                return f
        return name

    def _cleanup_zombies(self):
        """Kills any previous hanging processes and removes lock files."""
        try:
            # Kill by process names
            for proc in ["Xvfb", "x11vnc", "chromium-browser", "chromium", "google-chrome"]:
                subprocess.run(["pkill", "-9", "-f", proc], stderr=subprocess.DEV_NULL)
            
            # Cleanup X11 lock files
            display_num = self.display[1:]
            lock_files = [f"/tmp/.X{display_num}-lock", f"/tmp/.X11-unix/X{display_num}"]
            for lock in lock_files:
                if os.path.exists(lock):
                    try:
                        if os.path.isdir(lock): shutil.rmtree(lock)
                        else: os.remove(lock)
                    except: pass
            
            # Cleanup Chromium SingletonLock (Critical fix for Permission denied)
            singleton_lock = os.path.join(self.user_data_dir, "SingletonLock")
            if os.path.exists(singleton_lock):
                try: os.remove(singleton_lock)
                except: pass
            singleton_cookie = os.path.join(self.user_data_dir, "SingletonCookie")
            if os.path.exists(singleton_cookie):
                try: os.remove(singleton_cookie)
                except: pass
            singleton_socket = os.path.join(self.user_data_dir, "SingletonSocket")
            if os.path.exists(singleton_socket):
                try: os.remove(singleton_socket)
                except: pass
                
            sys.stderr.write(f"[{datetime.now()}] Cleanup completed\n")
        except Exception as e:
            sys.stderr.write(f"Cleanup error: {e}\n")

    def start(self):
        """Starts the virtual display and browser."""
        self._cleanup_zombies()
        time.sleep(1)

        xvfb_path = self._find_binary("Xvfb")
        vnc_path = self._find_binary("x11vnc")
        browser_path = self._find_binary("chromium-browser") or \
                       self._find_binary("chromium") or \
                       self._find_binary("google-chrome")

        if not xvfb_path or not vnc_path or not browser_path:
            sys.stderr.write(f"[{datetime.now()}] ERROR: Missing binaries: Xvfb={xvfb_path}, VNC={vnc_path}, Browser={browser_path}\n")
            return False

        # 1. Start Xvfb
        sys.stderr.write(f"[{datetime.now()}] Starting Xvfb on {self.display}...\n")
        try:
            self.xvfb_proc = subprocess.Popen([xvfb_path, self.display, "-screen", "0", "1280x1024x24"])
            time.sleep(2)
            if self.xvfb_proc.poll() is not None:
                raise Exception(f"Xvfb failed to start (code {self.xvfb_proc.returncode})")
        except Exception as e:
            sys.stderr.write(f"[{datetime.now()}] Xvfb Error: {str(e)}\n")
            return False

        os.environ["DISPLAY"] = self.display

        # 2. Start x11vnc
        sys.stderr.write(f"[{datetime.now()}] Starting x11vnc on port {self.port_vnc}...\n")
        try:
            self.vnc_proc = subprocess.Popen([
                vnc_path, "-display", self.display, "-nopw", "-localhost", "-rfbport", str(self.port_vnc), "-forever", "-shared"
            ])
            time.sleep(2)
            if self.vnc_proc.poll() is not None:
                raise Exception("x11vnc failed to start")
        except Exception as e:
            sys.stderr.write(f"[{datetime.now()}] x11vnc Error: {str(e)}\n")
            return False

        # 3. Start Chromium
        sys.stderr.write(f"[{datetime.now()}] Starting Chromium...\n")
        os.makedirs(self.user_data_dir, exist_ok=True)
        log_file = open("/tmp/chromium_remote.log", "w")
        
        try:
            self.browser_proc = subprocess.Popen([
                browser_path,
                "--no-sandbox",
                "--disable-setuid-sandbox",
                f"--user-data-dir={self.user_data_dir}",
                "--window-size=1280,1024",
                "--remote-debugging-port=9222",
                "--remote-debugging-address=127.0.0.1",
                "--disable-gpu",
                "--no-first-run",
                "--password-store=basic",
                "--lang=en-US",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--start-maximized",
                '--user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"',
                "https://notebooklm.google.com"
            ], stdout=log_file, stderr=log_file)
            time.sleep(3)
        except Exception as e:
            sys.stderr.write(f"[{datetime.now()}] Chromium Error: {str(e)}\n")

        return self.port_web

    async def take_screenshot(self):
        """Takes a screenshot of the current browser page via CDP."""
        from playwright.async_api import async_playwright
        import asyncio
        try:
            async with async_playwright() as p:
                browser = await asyncio.wait_for(
                    p.chromium.connect_over_cdp("http://127.0.0.1:9222"),
                    timeout=10
                )
                if not browser.contexts: return None
                page = browser.contexts[0].pages[0] if browser.contexts[0].pages else await browser.contexts[0].new_page()
                screenshot_bytes = await page.screenshot(type="jpeg", quality=60)
                await browser.close()
                return screenshot_bytes
        except Exception as e:
            sys.stderr.write(f"Screenshot Error: {e}\n")
            return None

    def get_logs(self):
        """Returns diagnostic logs."""
        logs = []
        if os.path.exists("/tmp/chromium_remote.log"):
            try:
                with open("/tmp/chromium_remote.log", "r") as f:
                    logs.append("--- CHROMIUM OUTPUT ---")
                    logs.append(f.read()[-2000:])
            except: pass
        return "\n".join(logs) if logs else "No logs found."

    def stop(self):
        """Stops all processes."""
        for proc in [self.browser_proc, self.vnc_proc, self.xvfb_proc]:
            if proc:
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                except:
                    pass
        self._cleanup_zombies()

    async def extract_cookies(self):
        """
        Extracts cookies from the running Chromium instance via CDP with a timeout.
        """
        from playwright.async_api import async_playwright
        import asyncio
        
        try:
            async with async_playwright() as p:
                # Connection with timeout
                try:
                    sys.stderr.write(f"[{datetime.now()}] Remote Auth: Connecting to browser via CDP...\n")
                    browser = await asyncio.wait_for(
                        p.chromium.connect_over_cdp("http://127.0.0.1:9222"),
                        timeout=15
                    )
                except asyncio.TimeoutError:
                    sys.stderr.write(f"[{datetime.now()}] Remote Auth: CDP connection timed out - browser might be unresponsive.\n")
                    return False
                
                # Get the first context/page
                if not browser.contexts:
                    sys.stderr.write(f"[{datetime.now()}] Remote Auth: No browser contexts found.\n")
                    await browser.close()
                    return False
                
                context = browser.contexts[0]
                cookies_list = await context.cookies()
                
                # NEW: Extract CSRF token (SNlM0e) and Session ID (FdrFJe)
                csrf_token = ""
                session_id = ""
                try:
                    # Find a notebooklm page or create one
                    page = None
                    for p in context.pages:
                        if "notebooklm.google.com" in p.url:
                            page = p
                            break
                    
                    if not page:
                        page = await context.new_page()
                        await page.goto("https://notebooklm.google.com", timeout=20000, wait_until="networkidle")
                    
                    # Wait and evaluate for CSRF
                    for attempt in range(5):
                        tokens = await page.evaluate("""() => {
                            const data = window.WIZ_global_data || {};
                            return {
                                at: data.SNlM0e || '',
                                sid: data.FdrFJe || new URLSearchParams(window.location.search).get('f.sid') || ''
                            };
                        }""")
                        csrf_token = tokens.get('at', '')
                        session_id = tokens.get('sid', '')
                        if csrf_token: break
                        await asyncio.sleep(2)
                        
                    # Fallback: Search in page content directly if evaluation lacks it
                    if not csrf_token:
                        html = await page.content()
                        import re
                        csrf_match = re.search(r'"SNlM0e":"([^"]+)"', html)
                        if csrf_match:
                            csrf_token = csrf_match.group(1)
                        sid_match = re.search(r'"FdrFJe":"([^"]+)"', html)
                        if sid_match:
                            session_id = sid_match.group(1)

                except Exception as e:
                    sys.stderr.write(f"[{datetime.now()}] Remote Auth: CSRF/SID extraction failed: {e}\n")

                await browser.close() 

                if cookies_list:
                    # Convert Playwright list[dict] to simple dict[name, value]
                    cookies_dict = {c['name']: c['value'] for c in cookies_list}
                    
                    # VALIDATION: Check for required Google cookies
                    required = ["SID", "HSID", "SSID", "APISID", "SAPISID"]
                    missing = [r for r in required if r not in cookies_dict]
                    if missing and len(missing) > 2: # Allow some missing if others exist
                         sys.stderr.write(f"[{datetime.now()}] Remote Auth: Missing critical cookies: {missing}\n")
                         return False

                    auth_dir = os.path.expanduser("~/.notebooklm-mcp")
                    os.makedirs(auth_dir, exist_ok=True)
                    auth_path = os.path.join(auth_dir, "auth.json")
                    
                    # Wrap in the format expected by AuthTokens.from_dict
                    auth_data = {
                        "cookies": cookies_dict,
                        "csrf_token": csrf_token,
                        "session_id": session_id,
                        "extracted_at": time.time()
                    }
                    
                    with open(auth_path, "w", encoding="utf-8") as f:
                        json.dump(auth_data, f, indent=2)
                    
                    sys.stderr.write(f"[{datetime.now()}] Remote Auth: SUCCESS ({len(cookies_dict)} cookies, CSRF: {'Found' if csrf_token else 'NOT FOUND'}).\n")
                    # If CSRF is still missing, it's a "soft" failure but we save what we have
                    return True if csrf_token else False
                else:
                    sys.stderr.write(f"[{datetime.now()}] Remote Auth: No cookies retrieved from browser.\n")
                    return False
        except Exception as e:
            sys.stderr.write(f"[{datetime.now()}] Remote Auth Extraction Failed: {str(e)}\n")
            return False
        return False

if __name__ == "__main__":
    # Test
    manager = RemoteBrowserManager()
    try:
        url = manager.start()
        print(f"Browser started at http://localhost:{url}")
        time.sleep(60)
    finally:
        manager.stop()
