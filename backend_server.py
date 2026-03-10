import os
import json
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import firebase_admin
from firebase_admin import credentials, auth
from typing import Optional
import asyncio
from datetime import datetime
from execution.notebooklm_query import get_client
from remote_browser_manager import RemoteBrowserManager

app = FastAPI(title="Clinic Assistant API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase Admin
# Note: You need to place your firebase-adminsdk.json in the root directory
fb_creds_path = os.path.join(os.path.dirname(__file__), "firebase-adminsdk.json")
if os.path.exists(fb_creds_path):
    cred = credentials.Certificate(fb_creds_path)
    firebase_admin.initialize_app(cred)
else:
    print("WARNING: firebase-adminsdk.json not found. Auth features will be limited.")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "modules_config.json")
WHITELIST_PATH = os.path.join(os.path.dirname(__file__), "whitelist.json")
ADMIN_EMAIL = "yduoc407@gmail.com"
EXECUTION_SCRIPT = os.path.join(os.path.dirname(__file__), "execution", "notebooklm_query.py")

class ChatRequest(BaseModel):
    module_id: str
    message: str

class ModuleConfig(BaseModel):
    name: str
    description: str
    notebook_id: str

class ConfigUpdate(BaseModel):
    modules: dict[str, ModuleConfig]

async def verify_firebase_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.split("Bearer ")[1]
    try:
        # Use verify_id_token ONLY if firebase-adminsdk.json is present
        if firebase_admin._apps:
            decoded_token = auth.verify_id_token(token)
            return {
                "uid": decoded_token["uid"],
                "email": decoded_token.get("email"),
                "is_admin": decoded_token.get("email") == ADMIN_EMAIL
            }
        else:
            # Fallback for local testing if SDK is still missing
            return {"uid": "local_test_user", "email": "admin@localhost", "is_admin": "admin@localhost" == ADMIN_EMAIL}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def load_whitelist():
    if not os.path.exists(WHITELIST_PATH):
        return []
    with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_whitelist(emails):
    with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
        json.dump(emails, f, indent=2, ensure_ascii=False)

@app.get("/api/modules")
async def get_modules():
    config = load_config()
    return config["modules"]

@app.post("/api/admin/modules")
async def update_modules(config_update: ConfigUpdate, user: dict = Depends(verify_firebase_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = {"modules": {k: v.dict() for k, v in config_update.modules.items()}}
    save_config(config)
    return {"status": "success", "message": "Configuration updated"}

@app.post("/api/admin/reauth")
async def reauth_notebooklm(user: dict = Depends(verify_firebase_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    try:
        # Run notebooklm-mcp-auth using subprocess
        # Working directory is the root of the project to ensure correct context if needed
        cwd = os.path.dirname(__file__)
        process = subprocess.run(
            ["notebooklm-mcp-auth"],
            capture_output=True,
            text=True,
            cwd=cwd
        )
        
        if process.returncode == 0:
            return {"status": "success", "message": "Xác thực NotebookLM thành công:\n" + process.stdout}
        else:
            return {"status": "error", "message": "Lỗi xác thực NotebookLM:\n" + process.stderr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi chạy lệnh xác thực: {str(e)}")

@app.get("/api/admin/whitelist")
async def get_whitelist(user: dict = Depends(verify_firebase_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    if not os.path.exists(WHITELIST_PATH):
        return []
    with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/admin/whitelist")
async def add_to_whitelist(data: dict, user: dict = Depends(verify_firebase_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Thiếu email")
    
    whitelist = []
    if os.path.exists(WHITELIST_PATH):
        with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
            whitelist = json.load(f)
    
    if email not in whitelist:
        whitelist.append(email)
        with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
            json.dump(whitelist, f, indent=2, ensure_ascii=False)
    
    return {"status": "success", "message": f"Đã thêm {email} vào danh sách"}

@app.delete("/api/admin/whitelist/{email}")
async def remove_from_whitelist(email: str, user: dict = Depends(verify_firebase_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    if os.path.exists(WHITELIST_PATH):
        with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
            whitelist = json.load(f)
        if email in whitelist:
            whitelist.remove(email)
            with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
                json.dump(whitelist, f, indent=2, ensure_ascii=False)
    return {"status": "success", "message": f"Đã xóa {email} khỏi danh sách"}

@app.get("/api/check-whitelist")
async def check_whitelist(email: str):
    whitelist = load_whitelist()
    return {"allowed": email in whitelist}

@app.post("/api/admin/upload-auth")
async def upload_auth_file(file: UploadFile = File(...), user: dict = Depends(verify_firebase_token)):
    """Upload auth.json file to update NotebookLM authentication credentials."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file .json")
    try:
        contents = await file.read()
        # Validate JSON structure
        json.loads(contents)
        # Save to the correct path
        auth_dir = os.path.expanduser("~/.notebooklm-mcp")
        os.makedirs(auth_dir, exist_ok=True)
        auth_path = os.path.join(auth_dir, "auth.json")
        with open(auth_path, "wb") as f:
            f.write(contents)
        return {"status": "success", "message": "✅ File auth.json đã được cập nhật thành công! NotebookLM sẽ sử dụng thông tin đăng nhập mới từ bây giờ."}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="File không phải JSON hợp lệ. Hãy chắc chắn bạn chọn đúng file auth.json.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu file: {str(e)}")

@app.get("/api/admin/auth-status")
async def get_auth_status(user: dict = Depends(verify_firebase_token)):
    """Check the status of the NotebookLM auth file."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    auth_path = os.path.expanduser("~/.notebooklm-mcp/auth.json")
    if os.path.exists(auth_path):
        mtime = os.path.getmtime(auth_path)
        last_updated = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        return {"exists": True, "last_updated": last_updated}
    return {"exists": False, "last_updated": None}


@app.get("/api/admin/test-auth")
async def test_auth(user: dict = Depends(verify_firebase_token)):
    """Manually test if the current NotebookLM session is still valid."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = load_config()
    # Use any available notebook ID for testing
    nb_id = next(iter(config["modules"].values()))["notebook_id"] if config["modules"] else None
    
    if not nb_id:
        return {"status": "error", "message": "No notebooks configured to test with."}

    client = get_client()
    if not client:
        return {"status": "error", "message": "Authentication file (auth.json) not found."}

    try:
        # Try a lightweight operation: get notebook metadata
        client.get_notebook(nb_id)
        return {"status": "success", "message": "Kết nối tốt! Phiên làm việc vẫn đang hoạt động."}
    except Exception as e:
        error_msg = str(e)
        if "Authentication expired" in error_msg:
            return {"status": "expired", "message": "Phiên làm việc đã hết hạn. Hãy upload auth.json mới."}
        return {"status": "error", "message": f"Lỗi kết nối: {error_msg}"}

async def heartbeat_task():
    """Background task to keep NotebookLM session alive."""
    while True:
        try:
            config = load_config()
            if config["modules"]:
                nb_id = next(iter(config["modules"].values()))["notebook_id"]
                client = get_client()
                if client:
                    # Just a small ping to keep session warm
                    client.get_notebook(nb_id)
                    sys.stderr.write(f"[{datetime.now()}] Heartbeat: Session refreshed successfully.\n")
        except Exception as e:
            sys.stderr.write(f"[{datetime.now()}] Heartbeat failed: {str(e)}\n")
            pass
        
        # Sleep for 30 minutes
        await asyncio.sleep(1800)

@app.on_event("startup")
async def startup_event():
    # Start heartbeat in background
    asyncio.create_task(heartbeat_task())

# Browser instance manager
browser_manager = RemoteBrowserManager()

@app.post("/api/admin/browser/start")
async def start_browser(user: dict = Depends(verify_firebase_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    try:
        port = browser_manager.start()
        # Return the noVNC URL. Assuming it's accessed via the same host
        # In production, this might need a secure tunnel or proxy path
        return {"status": "success", "port": port, "message": "Browser started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/browser/stop")
async def stop_browser(user: dict = Depends(verify_firebase_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    browser_manager.stop()
    return {"status": "success", "message": "Browser stopped"}

@app.post("/api/admin/browser/extract")
async def extract_browser_cookies(user: dict = Depends(verify_firebase_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    success = await browser_manager.extract_cookies()
    if success:
        return {"status": "success", "message": "✅ Đã tự động cập nhật auth.json từ trình duyệt ảo!"}
    else:
        return {"status": "error", "message": "❌ Lỗi: Không thể lấy chìa khóa. Bạn đã đăng nhập vào NotebookLM chưa?"}

@app.websocket("/api/admin/browser/ws")
async def vnc_proxy(websocket: WebSocket, token: Optional[str] = None):
    # Authenticate via token query param (since WS doesn't support custom headers easily in all clients)
    if not token:
        await websocket.close(code=4003)
        return
    
    try:
        decoded_token = auth.verify_id_token(token)
        if decoded_token.get("email") != ADMIN_EMAIL:
            await websocket.close(code=4003)
            return
    except:
        await websocket.close(code=4003)
        return

    await websocket.accept(subprotocol="binary")
    
    try:
        # Tunnel to local VNC server (RFB)
        reader, writer = await asyncio.open_connection("127.0.0.1", 5901)
        
        async def ws_to_vnc():
            try:
                while True:
                    data = await websocket.receive_bytes()
                    writer.write(data)
                    await writer.drain()
            except:
                pass

        async def vnc_to_ws():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data: break
                    await websocket.send_bytes(data)
            except:
                pass

        await asyncio.gather(ws_to_vnc(), vnc_to_ws())
    except Exception as e:
        print(f"VNC Proxy Error: {e}")
    finally:
        await websocket.close()

@app.get("/api/admin/browser/view")
async def get_browser_view():
    """Returns a simple HTML page that embeds noVNC from a CDN."""
    return StreamingResponse(asyncio.to_thread(lambda: f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Remote Browser View</title>
        <style>body, html, #vnc {{ width: 100%; height: 100%; margin: 0; background: #000; overflow: hidden; }}</style>
    </head>
    <body>
        <div id="vnc"></div>
        <script type="module">
            import RFB from 'https://cdn.jsdelivr.net/npm/@novnc/novnc@1.3.0/core/rfb.js';
            const url = new URL(window.location);
            const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsPath = url.pathname.replace('/view', '/ws');
            // We'll need the token from the parent or storage
            const token = localStorage.getItem('fb_id_token') || url.searchParams.get('token');
            const rfb = new RFB(document.getElementById('vnc'), `${{protocol}}//${{url.host}}${{wsPath}}?token=${{token}}`, {{
                wsProtocols: ['binary']
            }});
            rfb.scaleViewport = true;
            rfb.resizeSession = true;
        </script>
    </body>
    </html>
    """.encode('utf-8')), media_type="text/html")

# In-memory session store
conversation_map = {}

from fastapi.responses import StreamingResponse

@app.post("/api/chat")
async def chat(request: ChatRequest, user=Depends(verify_firebase_token)):
    config = load_config()
    if request.module_id not in config["modules"]:
        raise HTTPException(status_code=404, detail="Module not found")
    
    notebook_id = config["modules"][request.module_id]["notebook_id"]
    
    # Isolate conversation per user and per module
    user_key = f"{user['uid']}_{request.module_id}"
    conversation_id = conversation_map.get(user_key, "NEW")
    
    def generate_streaming_response():
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            # Pass conversation_id to the script, bufsize=1 for line buffering
            process = subprocess.Popen(
                ["python", "-u", EXECUTION_SCRIPT, notebook_id, conversation_id, request.message],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                encoding="utf-8",
                env=env
            )

            # Read stdout line by line as it is generated without read-ahead buffering
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                
                try:
                    data = json.loads(line)
                    # intercept meta to save conversation_id per user
                    if data.get("type") == "meta" and data.get("conversation_id"):
                        conversation_map[user_key] = data["conversation_id"]
                    
                    # Yield SSE formatted data
                    yield f"data: {json.dumps(data)}\n\n".encode("utf-8")
                except json.JSONDecodeError:
                    # Yield raw error line if it doesn't parse as JSON
                    yield f"data: {json.dumps({'type': 'error', 'error': line.strip()})}\n\n".encode("utf-8")

            process.stdout.close()
            process.wait()
            
            if process.returncode != 0:
                stderr = process.stderr.read()
                yield f"data: {json.dumps({'type': 'error', 'error': stderr or 'Execution failed'})}\n\n".encode("utf-8")

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n".encode("utf-8")

    return StreamingResponse(generate_streaming_response(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8042)
