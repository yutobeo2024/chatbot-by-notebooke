# Hướng dẫn: Kết nối Domain → Cloudflare Tunnel → Cập nhật Auth

> **Dành cho người không chuyên về kỹ thuật.**
> Tài liệu này ghi lại đúng những bước đã làm thành công, giải thích dễ hiểu.

---

## Phần 1: Tại sao cần làm những bước này?

Khi bạn có website (frontend) chạy trên Netlify và một máy chủ (VPS) chạy phần xử lý phía sau (backend), có một vấn đề:

> Netlify dùng giao thức **HTTPS** (bảo mật, có mã hóa). Máy chủ VPS chỉ chạy **HTTP** (không có mã hóa). Trình duyệt hiện đại **cấm** website HTTPS gọi sang dịch vụ HTTP. Đây gọi là lỗi "**Mixed Content**".

**Giải pháp:** Dùng **Cloudflare Tunnel** để tạo một "đường hầm" bảo mật, cho phép VPS nhận yêu cầu qua HTTPS mà không cần cài đặt phức tạp.

---

## Phần 2: Chuẩn bị

Bạn cần có sẵn:
- Một **tên miền** đã mua (ví dụ: `ydsgchatbot.io.vn` mua tại iNET.vn)
- Một **tài khoản Cloudflare** miễn phí tại [cloudflare.com](https://cloudflare.com)
- Đã SSH được vào **máy chủ VPS** (ví dụ: `beodev@180.93.137.17`)
- Đã cài sẵn `cloudflared` trên VPS

---

## Phần 3: Đưa Domain vào Cloudflare

### Bước 1: Cài đặt Domain trên Cloudflare

1. Đăng nhập [dash.cloudflare.com](https://dash.cloudflare.com)
2. Bấm **"Onboard a domain"** (hoặc **"Add a domain"**)
3. Nhập tên miền của bạn (ví dụ: `ydsgchatbot.io.vn`)
4. Chọn gói **Free** → Bấm **Continue**
5. Ở màn hình xem DNS sẵn có → Bấm **Continue** (bỏ qua)
6. Cloudflare sẽ đưa ra **2 địa chỉ Nameserver** mới

> **Nameserver là gì?** Hãy nghĩ như thế này: Tên miền là "bảng tên công ty", còn Nameserver là "người quản lý danh bạ điện thoại" cho tên miền đó. Thay Nameserver nghĩa là chuyển quyền quản lý danh bạ từ iNET sang Cloudflare.

### Bước 2: Thay Nameserver tại iNET (Nhà cung cấp tên miền)

1. Đăng nhập [portal.inet.vn](https://portal.inet.vn)
2. Vào **Tên miền** → Chọn domain của bạn
3. Tìm mục **Quản lý DNS và bản ghi**
4. Nhập 2 địa chỉ Nameserver từ Cloudflare vào (xóa các địa chỉ cũ của iNET)
5. Bấm **Cập nhật DNS** để lưu

### Bước 3: Xác nhận với Cloudflare

Quay lại Cloudflare → Cuộn xuống cuối trang → Bấm **"I updated my nameservers"**

> **Thời gian chờ:** Thường mất 5-30 phút để Cloudflare xác nhận. Bạn sẽ nhận email thông báo khi domain chuyển sang trạng thái **Active** (màu xanh lá).

---

## Phần 4: Tạo Cloudflare Tunnel

Khi domain đã **Active** trên Cloudflare, SSH vào VPS và chạy lần lượt các lệnh sau.

### Bước 1: Tạo tunnel mới
```bash
cloudflared tunnel create chatbot-api
```
Lệnh này sẽ in ra **Tunnel ID** (ví dụ: `847de6ca-57cb-4612-8fa9-deff650d2f28`). **Ghi lại con số này.**

### Bước 2: Mở file cấu hình
```bash
nano ~/.cloudflared/config.yml
```

Dán đoạn nội dung sau vào (thay `YOUR_TUNNEL_ID` bằng con số Tunnel ID của bạn):
```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /home/beodev/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: api.ydsgchatbot.io.vn
    service: http://localhost:8042
  - service: http_status:404
```
Lưu file: **Ctrl+X** → Nhấn **Y** → Nhấn **Enter**

> **File này làm gì?** Nó nói với Cloudflare Tunnel: "Khi ai đó truy cập `api.ydsgchatbot.io.vn`, hãy chuyển yêu cầu đó xuống cổng 8042 của máy chủ (nơi Backend fastAPI đang lắng nghe)."

### Bước 3: Copy file cấu hình vào thư mục hệ thống
```bash
sudo mkdir -p /etc/cloudflared
sudo cp /home/beodev/.cloudflared/config.yml /etc/cloudflared/config.yml
```

### Bước 4: Cài đặt Tunnel chạy vĩnh viễn
```bash
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```
Nếu thấy **`active (running)`** là thành công!

### Bước 5: Thêm địa chỉ DNS cho tên miền phụ

Quay lại Cloudflare Dashboard → Chọn domain → **DNS** → **Add record**:
- **Type:** `CNAME`
- **Name:** `api`
- **Target:** `YOUR_TUNNEL_ID.cfargotunnel.com`
- **Proxy status:** 🟠 Proxied (bật cam lên)
- Bấm **Save**

> **Ghi chú:** Sau bước này, URL `https://api.ydsgchatbot.io.vn` sẽ kết nối được tới Backend VPS qua HTTPS bảo mật hoàn toàn.

---

## Phần 5: Cập nhật Netlify dùng URL mới

1. Vào [app.netlify.com](https://app.netlify.com) → Chọn project
2. **Project configuration** → **Environment variables**
3. Đổi giá trị biến `VITE_API_URL` thành: `https://api.ydsgchatbot.io.vn`
4. Vào **Deploys** → **Trigger deploy** → **Clear cache and deploy site**

---

## Phần 6: Cập nhật Auth NotebookLM (Khi cần làm lại)

Google sẽ đăng xuất phiên của bạn sau vài tuần. Khi chatbot ngừng trả lời, bạn cần làm lại bước xác thực.

### Bước 1 - Trên máy tính Windows của bạn:
```powershell
notebooklm-mcp-auth
```
Chrome sẽ mở ra → Đăng nhập tài khoản Google → Đợi thấy "SUCCESS" → File xác thực được lưu tại `C:\Users\PT_1\.notebooklm-mcp\auth.json`.

### Bước 2 - Copy file xác thực lên VPS (Chọn 1 trong 2 cách)

#### Cách 1: Upload qua giao diện Web (Khuyên dùng - Dễ nhất)
1. Truy cập vào trang Admin của chatbot: `https://ydsg-chatbot.netlify.app/`
2. Đăng nhập tài khoản Admin.
3. Bấm nút **📂 Upload auth.json**.
4. Chọn file `auth.json` vừa tạo ở Bước 1.
5. Hệ thống sẽ tự động cập nhật lên VPS cho bạn. ✅

#### Cách 2: Dùng lệnh SCP (Nếu không vào được Web)
Mở một cửa sổ **PowerShell mới trên máy Windows**, rồi chạy:
```powershell
scp "C:\Users\PT_1\.notebooklm-mcp\auth.json" beodev@180.93.137.17:/home/beodev/.notebooklm-mcp/auth.json
```
Nhập mật khẩu VPS khi được hỏi.

---

### 🤔 Tại sao lệnh SCP phải chạy từ máy Windows, không phải từ VPS?

**SCP** (Secure Copy) là lệnh dùng để **gửi file từ máy này sang máy khác** qua mạng. Cú pháp của nó là:

```
scp [file_nguồn_trên_máy_này] [tên_người_dùng@địa_chỉ_máy_kia]:[đường_dẫn_đích]
```

File `auth.json` đang nằm trên **máy Windows của bạn** (`C:\Users\PT_1\...`).  
File cần được chuyển đến **VPS** (`/home/beodev/...`).

Vậy logic là: **"Tôi (Windows) đang cầm file, tôi cần gửi nó cho VPS."**
→ Lệnh SCP phải chạy từ **Windows** (người đang cầm file), không phải từ VPS.

Nếu bạn SSH vào VPS rồi chạy SCP trong đó, tức là bạn đang nói: **"VPS hãy tự đi lấy file từ... đường dẫn Windows `C:\Users\...`"** — điều này vô nghĩa vì VPS là máy Linux, không hiểu đường dẫn kiểu Windows, cũng không có quyền truy cập vào ổ C của máy tính bạn.

> 💡 **Gợi nhớ đơn giản:** "File đang ở đâu thì lệnh chạy từ đó." File ở Windows → lệnh chạy trên Windows.

---

## Tóm tắt quy trình

```
[Mua Domain] → [Thêm vào Cloudflare] → [Thay Nameserver tại iNET]
      ↓
[Chờ Cloudflare Active]
      ↓
[SSH vào VPS] → [Tạo Tunnel] → [Config] → [Chạy Service]
      ↓
[Thêm CNAME trên Cloudflare Dashboard]
      ↓
[Cập nhật VITE_API_URL trên Netlify] → [Deploy lại]
      ↓
[Copy auth.json từ Windows lên VPS bằng Web Upload hoặc SCP]
      ↓
✅ HỆ THỐNG HOÀN CHỈNH!
```
