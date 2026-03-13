# Hướng dẫn: Add Domain vào Cloudflare + Cloudflare Tunnel HTTPS

## Mục tiêu
Tạo URL HTTPS ổn định (ví dụ: `https://api.ydsg.vn`) trỏ vào Backend FastAPI trên VPS,
giải quyết lỗi Mixed Content khi Frontend Netlify (HTTPS) gọi API.

## Kiến trúc sau khi hoàn thành

```
Trình duyệt → https://api.yourdomain.com (HTTPS, ổn định)
                         ↓
              Cloudflare servers (SSL tự động)
                         ↓
              cloudflared daemon (chạy ngầm trên VPS)
                         ↓
              http://localhost:8042 (FastAPI nội bộ)
```

**Ưu điểm:** Không cần Nginx, không cần mở port 8042 ra internet, SSL miễn phí tự động.

---

## Bước 1: Mua tên miền

**Khuyến nghị mua tại Cloudflare Registrar** (giá gốc, không phí ẩn):
- Vào: https://www.cloudflare.com/products/registrar/
- Đăng ký tài khoản Cloudflare (miễn phí) → vào **Domain Registration** → tìm tên miền muốn mua.
- Thanh toán bằng thẻ Visa/Mastercard hoặc PayPal.

**Hoặc mua tên miền `.vn` tại:**
- P.A Vietnam: https://www.pavietnam.vn (~200-400k/năm)
- NhanhVN: https://www.nhanh.vn

_(Nếu mua ở nhà cung cấp khác, bạn vẫn dùng được Cloudflare nhưng cần thay Nameserver - xem Bước 2b bên dưới)_

---

## Bước 2: Add Domain vào Cloudflare

### 2a. Nếu mua domain tại Cloudflare Registrar
Domain tự động được quản lý trong Cloudflare, không cần làm gì thêm. Sang Bước 3.

### 2b. Nếu mua domain ở nơi khác (P.A Vietnam, NhanhVN, GoDaddy...)

1. Đăng nhập vào [Cloudflare Dashboard](https://dash.cloudflare.com) → **"Add a domain"**
2. Nhập tên miền của bạn (ví dụ: `ydsg.vn`) → Bấm **Continue**
3. Chọn gói **Free** → Bấm **Continue**
4. Cloudflare sẽ đưa cho bạn 2 địa chỉ **Nameserver** mới (ví dụ: `nina.ns.cloudflare.com`, `rick.ns.cloudflare.com`)
5. Đăng nhập vào nhà cung cấp domain của bạn → Tìm mục **Nameserver / DNS** → Thay 2 Nameserver cũ bằng 2 cái của Cloudflare
6. Chờ 5-30 phút để Cloudflare xác nhận. Trạng thái sẽ chuyển từ **Pending** sang **Active**.

---

## Bước 3: Tạo DNS Record trỏ về VPS

Trong Cloudflare Dashboard → Chọn domain của bạn → Tab **DNS** → **Records**:

1. Bấm **"Add record"**
2. Điền như sau:
   - **Type:** `A`
   - **Name:** `api` _(Tên miền phụ, sẽ tạo ra `api.yourdomain.com`)_
   - **IPv4 address:** `180.93.137.17`
   - **Proxy status:** Bật proxy 🟠 (Cloudflare làm proxy, SSL tự động)
3. Bấm **Save**

> Sau bước này, `https://api.yourdomain.com` đã trỏ đúng địa chỉ VPS của bạn. Tuy nhiên cần cấu hình Tunnel để yêu cầu không bị từ chối ở VPS.

---

## Bước 4: Cài và Cấu hình Cloudflare Tunnel trên VPS

Đăng nhập vào VPS qua SSH, thực hiện lần lượt:

### 4a. Cài đặt cloudflared
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

### 4b. Đăng nhập tài khoản Cloudflare
```bash
cloudflared tunnel login
```
Lệnh này sẽ in ra một URL. Bạn copy URL đó, mở trình duyệt, dán vào thanh địa chỉ và đăng nhập tài khoản Cloudflare của bạn, sau đó chọn domain muốn liên kết.

### 4c. Tạo Named Tunnel (tên cố định)
```bash
cloudflared tunnel create chatbot-api
```
Lệnh này tạo một tunnel tên `chatbot-api` và lưu file chứng chỉ vào `~/.cloudflared/`.  
Ghi lại **Tunnel ID** (dãy chữ số kiểu: `abc12345-...`) hiện ra trên màn hình.

### 4d. Tạo file cấu hình
```bash
nano ~/.cloudflared/config.yml
```

Dán nội dung sau (thay `YOUR_TUNNEL_ID` và `yourdomain.com`):
```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /home/beodev/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: api.yourdomain.com
    service: http://localhost:8042
  - service: http_status:404
```

Lưu lại (Ctrl+X → Y → Enter).

### 4e. Tạo DNS CNAME tự động
```bash
cloudflared tunnel route dns chatbot-api api.yourdomain.com
```
_(Lệnh này tự động thêm CNAME record vào Cloudflare DNS, thay thế cho record A đã tạo ở Bước 3 nếu có)_

### 4f. Test thử
```bash
cloudflared tunnel run chatbot-api
```
Mở trình duyệt vào `https://api.yourdomain.com/api/modules` - nếu thấy JSON trả về là thành công!

---

## Bước 5: Chạy Tunnel như Dịch vụ Hệ thống (Vĩnh viễn)

Nhấn **Ctrl+C** để dừng test, sau đó:

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```

Sau bước này, cả **FastAPI Backend** (service `chatbot`) và **Cloudflare Tunnel** (service `cloudflared`) đều chạy ngầm vĩnh viễn, tự khởi động sau khi VPS reboot.

---

## Bước 6: Cập nhật Cấu hình & Netlify

### 6a. Cấu hình bảo mật Backend (QUAN TRỌNG)

Khi bạn dùng domain riêng (`api.yourdomain.com`), bạn cần báo cho Backend biết để nó không chặn yêu cầu từ domain này:
1. Mở file `.env` trên VPS: `nano ~/chatbot-by-notebooke-master/.env`
2. Thêm hoặc sửa dòng sau:
   `ALLOWED_ORIGINS=https://ydsg-chatbot.netlify.app,https://api.yourdomain.com`
3. Lưu và khởi động lại Backend: `sudo systemctl restart chatbot`

### 6b. Cập nhật Netlify
1. Vào Netlify Dashboard → **Project configuration** → **Environment variables**
2. Sửa biến `VITE_API_URL`:
   - **Value:** `https://api.yourdomain.com`
3. Vào **Deploys** → **Trigger deploy** → **Clear cache and deploy site**

Sau khi deploy xong, giao diện Web `ydsg-chatbot.netlify.app` kết nối hoàn toàn qua HTTPS!

---

## Kiểm tra cuối cùng

1. Mở `https://ydsg-chatbot.netlify.app`
2. Bấm F12 → Console → Không còn lỗi `Mixed Content`
3. Danh sách chuyên khoa hiện ra đầy đủ
4. Chat trả lời bình thường ✅
