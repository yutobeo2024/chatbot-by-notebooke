# Project Context: Personal Clinic Assistant (Y DƯỢC SÀI GÒN)

## Project Overview
This project transforms a standard NotebookLM integration into a professional medical assistant for **Phòng khám Y Dược Sài Gòn**. It features a multi-module chat interface where each clinical department (Reception, Internal Medicine, etc.) is powered by a dedicated NotebookLM notebook.

## Key Components
- **`backend_server.py`**: A FastAPI backend that manages clinical modules, configurations, and proxies chat requests to the NotebookLM execution layer.
- **`frontend/`**: A React + Vite web application with a modern medical theme, module selection sidebar, and real-time chat.
- **`execution/notebooklm_query.py`**: The interface for querying NotebookLM using account cookies.
- **`modules_config.json`**: Dynamic mapping of clinic departments to Notebook IDs.
- **Admin Dashboard**: A secure interface (Firebase Auth) to manage Notebook IDs without editing code.

## Current Status
- **Version 2.1.0 Release**: Security Hardening + Frontend Modularization.
- **Session Memory**: Backend manages `conversation_id`, allowing follow-up questions.
- **Security Hardening**: Strict CORS policies and removal of auth bypass for production safety.
- **Modular Frontend**: Extracted reusable components (e.g., `TypingEffect`) and centralized configuration.
- Full medical theme implemented with smooth animations.
- Admin portal fully functional for live configuration updates.
- Firebase Authentication integrated for secure admin access.
- **Performance**: Uses isolated subprocess execution (stable) with context persistence.

## Technical Configuration
- **Backend Port**: 8042 (FastAPI)
- **Frontend Port**: 5173 (Vite)
- **Environment**: Uses `.env` for secrets (Admin Email, Allowed Origins). See `.env.example`.
- **Authentication**: Firebase Auth for Admin/Users & Session-based Auth for NotebookLM.
