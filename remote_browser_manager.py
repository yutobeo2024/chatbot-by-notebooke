import os
import subprocess
import time
import signal
import json
import shutil
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

    def start(self):
        """Starts the virtual display and browser."""
        # 1. Start Xvfb
        self.xvfb_proc = subprocess.Popen(["Xvfb", self.display, "-screen", "0", "1280x800x24"])
        os.environ["DISPLAY"] = self.display
        time.sleep(2)

        # 2. Start x11vnc
        self.vnc_proc = subprocess.Popen([
            "x11vnc", "-display", self.display, "-nopw", "-listen", "localhost", "-rfbport", str(self.port_vnc), "-forever"
        ])
        time.sleep(2)

        # 3. Start noVNC (websockify)
        # assuming novnc is installed in /usr/share/novnc or similar
        novnc_path = "/usr/share/novnc/utils/novnc_proxy"
        if not os.path.exists(novnc_path):
            novnc_path = shutil.which("novnc_proxy") or "novnc_proxy"

        self.novnc_proc = subprocess.Popen([
            novnc_path, "--vnc", f"localhost:{self.port_vnc}", "--listen", str(self.port_web)
        ])

        # 4. Start Chromium
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.browser_proc = subprocess.Popen([
            "chromium-browser",
            "--no-sandbox",
            f"--user-data-dir={self.user_data_dir}",
            "--window-size=1200,800",
            "https://notebooklm.google.com"
        ])

        return self.port_web

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
        Extracts cookies from the Chromium profile using Playwright and saves to auth.json.
        """
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            # We launch persistent context to access the user data dir used during login
            context = await p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=True
            )
            cookies = await context.cookies()
            await context.close()

            if cookies:
                auth_dir = os.path.expanduser("~/.notebooklm-mcp")
                os.makedirs(auth_dir, exist_ok=True)
                auth_path = os.path.join(auth_dir, "auth.json")
                
                with open(auth_path, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2)
                
                return True
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
