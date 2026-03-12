import asyncio
import json
import urllib.parse
from playwright.async_api import async_playwright
import os

async def test_api():
    async with async_playwright() as p:
        # Load auth
        with open(os.path.expanduser("~/.notebooklm-mcp/auth.json")) as f:
            auth_data = json.load(f)
            
        cookies = [{"name": k, "value": v, "domain": ".google.com", "path": "/"} for k, v in auth_data["cookies"].items() if isinstance(v, str)]
        
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies(cookies)
        
        page = await context.new_page()
        print("Page opened. Navigating to NotebookLM...")
        await page.goto("https://notebooklm.google.com")
        print("Navigation complete. Firing RPC...")
        
        # Execute the fetch directly in the browser context!
        rpc_id = "rLM1Ne"
        notebook_id = "8012aef4-3ab8-4624-a678-62f61415dd96"
        params_json = json.dumps([notebook_id], separators=(',', ':'))
        
        f_req = [[[rpc_id, params_json, None, "generic"]]]
        f_req_json = json.dumps(f_req, separators=(',', ':'))
        body = f"f.req={urllib.parse.quote(f_req_json, safe='')}&at={urllib.parse.quote(auth_data['csrf_token'], safe='')}&"
        
        url_params = {
            "rpcids": rpc_id,
            "source-path": "/",
            "bl": "boq_labs-tailwind-frontend_20260108.06_p0",
            "hl": "en",
            "rt": "c",
        }
        if auth_data.get("session_id"):
            url_params["f.sid"] = auth_data["session_id"]
            
        url = f"https://notebooklm.google.com/_/LabsTailwindUi/data/batchexecute?{urllib.parse.urlencode(url_params)}"
        
        res = await page.evaluate(f"""async () => {{
            const resp = await fetch("{url}", {{
                method: "POST",
                headers: {{
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                }},
                body: "{body}"
            }});
            return await resp.text();
        }}""")
        print("RESPONSE:")
        print(res[:500])
        await browser.close()

asyncio.run(test_api())
