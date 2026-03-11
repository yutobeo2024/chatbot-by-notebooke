
import os
import sys
import json
from notebooklm_mcp.api_client import NotebookLMClient, extract_cookies_from_chrome_export
from notebooklm_mcp.auth import load_cached_tokens

def get_client():
    # Diagnostic logging for VPS troubleshooting
    home = os.path.expanduser("~")
    auth_dir = os.path.join(home, ".notebooklm-mcp")
    auth_path = os.path.join(auth_dir, "auth.json")
    
    cookie_header = os.environ.get("NOTEBOOKLM_COOKIES", "")
    csrf_token = os.environ.get("NOTEBOOKLM_CSRF_TOKEN", "")
    session_id = os.environ.get("NOTEBOOKLM_SESSION_ID", "")
    cookies = {}

    if cookie_header:
        cookies = extract_cookies_from_chrome_export(cookie_header)
        sys.stderr.write(f"[DIAG] Using environment cookies ({len(cookies)} cookies)\n")
    else:
        # Check if auth file exists
        if not os.path.exists(auth_path):
            sys.stderr.write(f"[DIAG] auth.json NOT FOUND at {auth_path}\n")
            # Try a common alternative path just in case
            alt_path = "/home/beodev/.notebooklm-mcp/auth.json"
            if os.path.exists(alt_path):
                 sys.stderr.write(f"[DIAG] Found auth.json at ALTERNATIVE path: {alt_path}\n")
                 auth_path = alt_path

        if os.path.exists(auth_path):
            try:
                with open(auth_path) as f:
                    data = json.load(f)
                    cookies = data.get("cookies", {})
                    csrf_token = csrf_token or data.get("csrf_token", "")
                    session_id = session_id or data.get("session_id", "")
                    sys.stderr.write(f"[DIAG] Loaded auth.json from {auth_path} (CSRF: {'Found' if data.get('csrf_token') else 'Missing'}, Cookies: {len(cookies)})\n")
            except Exception as e:
                sys.stderr.write(f"[DIAG] Error reading auth.json: {e}\n")

        if not cookies:
            return None

    client = NotebookLMClient(cookies=cookies, csrf_token=csrf_token, session_id=session_id)
    
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    
    # 1. Patch the page fetch headers for refresh
    client._PAGE_FETCH_HEADERS.update({
        "User-Agent": UA,
        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec-ch-ua-platform": '"Windows"'
    })
    
    # 2. Monkey-patch the httpx client builder to use Windows headers
    import httpx
    def patched_get_client():
        if client._client is None:
            cookie_str = "; ".join(f"{k}={v}" for k, v in client.cookies.items())
            client._client = httpx.Client(
                headers={
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "Origin": client.BASE_URL,
                    "Referer": f"{client.BASE_URL}/",
                    "Cookie": cookie_str,
                    "X-Same-Domain": "1",
                    "User-Agent": UA,
                    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"'
                },
                timeout=30.0,
            )
        return client._client
        
    client._get_client = patched_get_client
    
    # 3. Force initialize httpx client with new patched headers
    client._get_client()
        
    return client

def query_notebook(notebook_id, query_text, conversation_id=None):
    client = get_client()
    if not client:
        print(json.dumps({"error": "Authentication required. Run 'notebooklm-mcp-auth'."}))
        sys.stdout.flush()
        return

    try:
        import uuid
        import urllib.parse

        # If no source_ids provided, get them from the notebook
        notebook_data = client.get_notebook(notebook_id)
        source_ids = client._extract_source_ids_from_notebook(notebook_data)

        # Determine if this is a new conversation or follow-up
        is_new_conversation = conversation_id is None
        if is_new_conversation:
            conversation_id = str(uuid.uuid4())
            conversation_history = None
        else:
            # Check if we have cached history for this conversation
            conversation_history = client._build_conversation_history(conversation_id)       

        # Build source IDs structure: [[[sid]]] for each source (3 brackets, not 4!)       
        sources_array = [[[sid]] for sid in source_ids] if source_ids else []

        # Query params structure (from network capture)
        params = [
            sources_array,
            query_text,
            conversation_history,  # None for new, history array for follow-ups
            [2, None, [1]],
            conversation_id,
        ]

        # Use compact JSON format matching Chrome (no spaces)
        params_json = json.dumps(params, separators=(",", ":"))

        f_req = [None, params_json]
        f_req_json = json.dumps(f_req, separators=(",", ":"))

        # URL encode with safe='' to encode all characters including /
        body_parts = [f"f.req={urllib.parse.quote(f_req_json, safe='')}"]
        if client.csrf_token:
            body_parts.append(f"at={urllib.parse.quote(client.csrf_token, safe='')}")        
        # Add trailing & to match NotebookLM's format
        body = "&".join(body_parts) + "&"

        client._reqid_counter += 100000  # Increment counter
        url_params = {
            "bl": os.environ.get("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260108.06_p0"),
            "hl": "en",
            "_reqid": str(client._reqid_counter),
            "rt": "c",
        }
        if client._session_id:
            url_params["f.sid"] = client._session_id

        query_string = urllib.parse.urlencode(url_params)
        url = f"{client.BASE_URL}{client.QUERY_ENDPOINT}?{query_string}"
        
        # Print initial metadata
        print(json.dumps({"type": "meta", "conversation_id": conversation_id}))
        sys.stdout.flush()

        current_answer_length = 0
        full_answer = ""

        # Stream the response
        with client._client.stream("POST", url, content=body, timeout=120.0) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                line = line.strip()
                if not line:
                    continue
                
                # Remove anti-XSSI prefix
                if line.startswith(")]}'"):
                    continue
                
                # Try to parse as byte count (indicates next line is JSON)
                try:
                    int(line)
                    continue
                except ValueError:
                    pass

                text, is_answer = client._extract_answer_from_chunk(line)
                
                if text and is_answer:
                    # The chunk usually contains the FULL string up to this point.
                    # We only want to yield the new delta to avoid repeating text.
                    if len(text) > current_answer_length:
                        delta = text[current_answer_length:]
                        full_answer = text
                        current_answer_length = len(text)
                        
                        print(json.dumps({"type": "chunk", "delta": delta}))
                        sys.stdout.flush()

        # Cache this turn for future follow-ups
        if full_answer:
            client._cache_conversation_turn(conversation_id, query_text, full_answer)        
        
        print(json.dumps({"type": "done"}))
        sys.stdout.flush()
        
    except Exception as e:
        print(json.dumps({"type": "error", "error": f"Lỗi truy vấn: {str(e)}"}))
        sys.stdout.flush()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        # Expect: notebook_id conversation_id query...
        # For new execution: conversation_id can be "NEW" or "None"
        print(json.dumps({"error": "Usage: python notebooklm_query.py <notebook_id> <conversation_id> <query>"}))
        sys.exit(1)
    
    nb_id = sys.argv[1]
    conv_id_arg = sys.argv[2]
    user_query = " ".join(sys.argv[3:])
    
    # Treat "NEW" or "None" as None
    real_conv_id = conv_id_arg if conv_id_arg not in ["NEW", "None", ""] else None
    
    query_notebook(nb_id, user_query, conversation_id=real_conv_id)
