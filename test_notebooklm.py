import os
import json
import traceback
from execution.notebooklm_query import get_client

client = get_client()
if not client:
    print("No client")
    exit(1)

print(f"Loaded client with {len(client.cookies)} cookies.")
print(f"CSRF Token: {client.csrf_token[:10]}... Length: {len(client.csrf_token)}")

try:
    print("Calling get_notebook...")
    # Using the Lễ Tân notebook ID
    notebook_id = "8012aef4-3ab8-4624-a678-62f61415dd96"
    data = client.get_notebook(notebook_id)
    print("SUCCESS!")
    print(data.title)
except Exception as e:
    print("FAILED with Exception:")
    traceback.print_exc()
