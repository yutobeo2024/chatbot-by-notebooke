import os
import json
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import firebase_admin
from firebase_admin import credentials, auth
from typing import Optional

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
    # TEMPORARY FIX FOR LOCAL TESTING:
    # Disable token verification since firebase-adminsdk.json is missing
    # if not authorization or not authorization.startswith("Bearer "):
    #     raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    # token = authorization.split("Bearer ")[1]
    # try:
    #     decoded_token = auth.verify_id_token(token)
    #     return decoded_token
    # except Exception as e:
    #     raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    # Just return a dummy user object so the dependent functions don't crash
    return {"uid": "local_test_user", "email": "admin@localhost"}

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

@app.get("/api/modules")
async def get_modules():
    config = load_config()
    return config["modules"]

@app.post("/api/admin/modules")
async def update_modules(config_update: ConfigUpdate, user=Depends(verify_firebase_token)):
    # Basic Admin check: You can restrict this to specific emails or custom claims
    # if user.get("email") != "your-admin-email@example.com":
    #     raise HTTPException(status_code=403, detail="Permission denied")
    
    config = {"modules": {k: v.dict() for k, v in config_update.modules.items()}}
    save_config(config)
    return {"status": "success", "message": "Configuration updated"}

@app.post("/api/admin/reauth")
async def reauth_notebooklm(user=Depends(verify_firebase_token)):
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

@app.post("/api/admin/upload-auth")
async def upload_auth_file(file: UploadFile = File(...), user=Depends(verify_firebase_token)):
    """Upload auth.json file to update NotebookLM authentication credentials."""
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
async def get_auth_status(user=Depends(verify_firebase_token)):
    """Check the status of the NotebookLM auth file."""
    auth_path = os.path.expanduser("~/.notebooklm-mcp/auth.json")
    if os.path.exists(auth_path):
        mtime = os.path.getmtime(auth_path)
        from datetime import datetime
        last_updated = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        return {"exists": True, "last_updated": last_updated}
    return {"exists": False, "last_updated": None}


# In-memory session store: { "module_id": "conversation_id" }
# Note: In a production app with multiple users, this should be { "user_id_module_id": "conversation_id" }
conversation_map = {}

from fastapi.responses import StreamingResponse
import asyncio

@app.post("/api/chat")
async def chat(request: ChatRequest):
    config = load_config()
    if request.module_id not in config["modules"]:
        raise HTTPException(status_code=404, detail="Module not found")
    
    notebook_id = config["modules"][request.module_id]["notebook_id"]
    
    # Get existing conversation ID or "NEW"
    conversation_id = conversation_map.get(request.module_id, "NEW")
    
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
                    # intercept meta to save conversation_id
                    if data.get("type") == "meta" and data.get("conversation_id"):
                        conversation_map[request.module_id] = data["conversation_id"]
                    
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
