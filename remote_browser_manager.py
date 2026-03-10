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
        self.user_data_dir = os.path.expanduser("~/.notebooklm-remote-profile")

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
        """Kills any previous hanging processes."""
        try:
            # Kill by process names
            subprocess.run(["pkill", "-f", "Xvfb :99"], stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-f", "x11vnc.*:5901"], stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-f", "chromium-browser"], stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-f", "novnc_proxy"], stderr=subprocess.DEVNULL)
            
            # Cleanup X11 lock files
            for f in ["/tmp/.X99-lock", "/tmp/.X11-unix/X99"]:
                if os.path.exists(f):
                    try: os.remove(f)
                    except: pass
        except:
            pass

    def start(self):
        """Starts the virtual display and browser."""
        self._cleanup_zombies()
        time.sleep(1)

        xvfb_path = self._find_binary("Xvfb")
        vnc_path = self._find_binary("x11vnc")
        browser_path = self._find_binary("chromium-browser") or self._find_binary("chromium")

        # 1. Start Xvfb (Higher resolution for better experience)
        sys.stderr.write(f"[{datetime.now()}] Starting Xvfb on {self.display}...\n")
        self.xvfb_proc = subprocess.Popen([xvfb_path, self.display, "-screen", "0", "1280x1024x24"])
        os.environ["DISPLAY"] = self.display
        time.sleep(2)

        # 2. Start x11vnc
        sys.stderr.write(f"[{datetime.now()}] Starting x11vnc on port {self.port_vnc}...\n")
        self.vnc_proc = subprocess.Popen([
            vnc_path, "-display", self.display, "-nopw", "-listen", "localhost", "-rfbport", str(self.port_vnc), "-forever", "-shared"
        ])
        time.sleep(2)

        # 3. Start Chromium with logging
        sys.stderr.write(f"[{datetime.now()}] Starting Chromium at {browser_path}...\n")
        os.makedirs(self.user_data_dir, exist_ok=True)
        
        # Open log file
        log_file = open("/tmp/chromium_remote.log", "w")
        
        self.browser_proc = subprocess.Popen([
            browser_path,
            "--no-sandbox",
            f"--user-data-dir={self.user_data_dir}",
            "--window-size=1200,900",
            "--remote-debugging-port=9222",
            "--remote-debugging-address=127.0.0.1",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--password-store=basic",
            "https://notebooklm.google.com"
        ], stdout=log_file, stderr=log_file)

        return self.port_web

    def get_logs(self):
        """Returns the last lines of the chromium log."""
        if os.path.exists("/tmp/chromium_remote.log"):
            with open("/tmp/chromium_remote.log", "r") as f:
                return f.read()[-2000:]
        return "No logs found."

    def stop(self):
        """Stops all processes."""
        for proc in [self.browser_proc, self.novnc_proc, self.vnc_proc, self.xvfb_proc]:
            if proc:
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                except:
                    pass
        
        # Cleanup locks
        lock_file = f"/tmp/.X{self.display[1:]}-lock"
        if os.path.exists(lock_file):
            os.remove(lock_file)

    async def extract_cookies(self):
        """
        Extracts cookies from the running Chromium instance via CDP.
        """
        from playwright.async_api import async_playwright
        import sys
        
        try:
            async with async_playwright() as p:
                # Connect to the already running browser via CDP
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                # Get the first context/page
                if not browser.contexts:
                    return False
                
                context = browser.contexts[0]
                cookies = await context.cookies()
                await browser.close() # This closes the CDP connection, not necessarily the browser process

                if cookies:
                    auth_dir = os.path.expanduser("~/.notebooklm-mcp")
                    os.makedirs(auth_dir, exist_ok=True)
                    auth_path = os.path.join(auth_dir, "auth.json")
                    
                    with open(auth_path, "w", encoding="utf-8") as f:
                        json.dump(cookies, f, indent=2)
                    
                    sys.stderr.write(f"[{datetime.now()}] Remote Auth: Cookies extracted successfully.\n")
                    return True
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
