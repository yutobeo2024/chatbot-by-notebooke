# Directive: Clinic Assistant Querying

## Goal
Query the NotebookLM system based on specific clinic modules (Receptionist, Clinical Departments, etc.) to get accurate medical and procedural information.

## Inputs
- `module_id`: The ID of the clinic department (e.g., `reception`, `internal_medicine`).
- `query`: The user's question.

## Tools to Use
- `execution/notebooklm_query.py`: The deterministic script that handles the HTTP communication with NotebookLM.

## Flow
1. Identify the `notebook_id` associated with the `module_id` (from mapping config).
2. Call `execution/notebooklm_query.py` with the `notebook_id` and the `query`.
3. Receive the raw response and format it for the chat interface.

## Edge Cases
- **Session Expired**: If the script returns an authentication error, notify the user to run `notebooklm-mcp-auth`.
- **Notebook Not Found**: Log the error and suggest checking the mapping configuration.
