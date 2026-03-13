# Clinic Assistant (Y DƯƠC SÀI GÒN) - NotebookLM Powered

Ứng dụng trợ lý y khoa chuyên nghiệp dựa trên tích hợp NotebookLM, được thiết kế cho **Phòng khám Y Dược Sài Gòn**.

## 🚀 Tính năng nổi bật

- **Đa chuyên khoa**: Mỗi khoa lâm sàng (Nội, Ngoại, Sản, Nha...) được vận hành bởi một Notebook riêng biệt.
- **Session Memory**: Ghi nhớ ngữ cảnh hội thoại, cho phép hỏi đáp liên tục một cách tự nhiên.
- **Medical UI**: Giao diện React hiện đại, tối ưu cho lĩnh vực y tế với hiệu ứng gõ chữ thời gian thực.
- **Admin Dashboard**: Quản lý Notebook IDs, Whitelist người dùng và xác thực NotebookLM trực tiếp từ web.
- **Bảo mật**: Tích hợp Firebase Auth và cơ chế thắt chặt CORS.

## 🛠️ Cài đặt & Thiết lập

### 1. Yêu cầu hệ thống
- Python 3.10+ & Node.js 18+
- Tài khoản Google có quyền truy cập NotebookLM.
- Firebase Project (cho Auth).

### 2. Cài đặt Backend
```bash
pip install -r requirements.txt
# Copy file ví dụ cấu hình
cp .env.example .env
# Chỉnh sửa .env với thông tin của bạn (ADMIN_EMAIL, ALLOWED_ORIGINS)
```

### 3. Cài đặt Frontend
```bash
cd frontend
npm install
# Cấu hình VITE_API_URL trong .env
npm run dev
```

### 4. Xác thực NotebookLM
Chạy lệnh xác thực lần đầu trên máy tính cá nhân để lấy `auth.json`:
```bash
notebooklm-mcp-auth
```
Sau đó upload file `auth.json` qua giao diện **Admin Dashboard**.

## 📂 Cấu trúc dự án

- `backend_server.py`: FastAPI backend quản lý module và proxy requests.
- `frontend/`: Ứng dụng React + Vite.
- `execution/`: Chứa logic truy vấn NotebookLM.
- `modules_config.json`: Cấu hình động cho các chuyên khoa.

## 🔐 Bảo mật (Audit)
Dự án đã qua kiểm tra (Audit) và triển khai các biện pháp bảo mật:
- Chặn Bypass Auth khi thiếu SDK.
- Giới hạn Origins gọi API.
- Quản lý secrets qua biến môi trường.

## 📄 Tài liệu hướng dẫn
- [TUTORIAL_CloudflareTunnel.md](./TUTORIAL_CloudflareTunnel.md)
- [TUTORIAL_Reauth_NotebookLM.md](./TUTORIAL_Reauth_NotebookLM.md)
- [TUTORIAL_VPS_Cloudflare_SCP.md](./TUTORIAL_VPS_Cloudflare_SCP.md)
