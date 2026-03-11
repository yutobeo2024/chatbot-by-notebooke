import json
import urllib.parse
import httpx
import os
import sys

# Load auth
auth_path = os.path.expanduser("~/.notebooklm-mcp/auth.json")
with open(auth_path) as f:
    auth_data = json.load(f)

cookies = auth_data["cookies"]
csrf_token = auth_data["csrf_token"]
session_id = auth_data.get("session_id", "")

print(f"Loaded {len(cookies)} cookies.")
print(f"CSRF: {csrf_token}")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

client = httpx.Client(
    headers={
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": "https://notebooklm.google.com",
        "Referer": "https://notebooklm.google.com/",
        "Cookie": cookie_str,
        "X-Same-Domain": "1",
        "User-Agent": UA,
        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    },
    timeout=30.0,
)

# Fetch homepage to get a fresh CSRF token
import re
print("Refreshing CSRF token...")
resp_home = client.get("https://notebooklm.google.com/")
csrf_match = re.search(r'"SNlM0e":"([^"]+)"', resp_home.text)
if csrf_match:
    csrf_token = csrf_match.group(1)
    print(f"Refreshed CSRF: {csrf_token}")
else:
    print("FAILED to refresh CSRF token!")


rpc_id = "rLM1Ne" # get_notebook
notebook_id = "8012aef4-3ab8-4624-a678-62f61415dd96"
params_json = json.dumps([notebook_id], separators=(',', ':'))

f_req = [[[rpc_id, params_json, None, "generic"]]]
f_req_json = json.dumps(f_req, separators=(',', ':'))

# URL encode (safe='' encodes all characters including /)
body_parts = [f"f.req={urllib.parse.quote(f_req_json, safe='')}"]
body_parts.append(f"at={urllib.parse.quote(csrf_token, safe='')}")
body = "&".join(body_parts) + "&"

params = {
    "rpcids": rpc_id,
    "source-path": "/",
    "bl": "boq_labs-tailwind-frontend_20260108.06_p0",
    "hl": "en",
    "rt": "c",
}
if session_id:
    params["f.sid"] = session_id

url = f"https://notebooklm.google.com/_/LabsTailwindUi/data/batchexecute?{urllib.parse.urlencode(params)}"

print("Making request...")
resp = client.post(url, content=body)
print(f"HTTP Status: {resp.status_code}")
print("Response preview:")
print(resp.text[:1000])

if "16" in resp.text and "generic" in resp.text:
    print("WARNING: FOUND RPC ERROR 16 IN RESPONSE TEXT!")
