# TÀI LIỆU HỌC TẬP: Tích hợp nút "Kết nối lại NotebookLM" vào Web UI

Tài liệu này giải thích chi tiết vấn đề, tư duy giải quyết và các bước code thực tế để đưa lệnh CLI (Command Line Interface) lên giao diện Web, giúp người dùng cuối (Admin) dễ dàng thao tác mà không cần kiến thức về lập trình hay Terminal.

---

## 1. Hiểu Vấn Đề (The Problem)

**Hoàn cảnh:** 
Giao tiếp giữa ứng dụng của chúng ta và NotebookLM dựa trên "Cookie" và "Token" sinh ra từ trình duyệt. Tuy nhiên, Google có cơ chế bảo mật khiến các Token này sẽ **hết hạn** sau một khoảng thời gian (khoảng 1 tuần). 

**Triệu chứng:**
Khi Token hết hạn, bất kỳ câu hỏi nào gửi từ Chatbot lên NotebookLM đều bị từ chối với mã lỗi `400 Bad Request`.

**Cách khắc phục thủ công cũ:**
Người quản trị phải mở màn hình đen (Terminal/Command Prompt) và gõ lệnh `notebooklm-mcp-auth`. Lệnh này là một script Python có nhiệm vụ mở Chrome lên, tự động trích xuất Token mới nhất và lưu đè vào file cấu hình.

**Nhu cầu:**
Thao tác thủ công quá phức tạp với người dùng không chuyên. Chúng ta cần một nút bấm "Kết nối lại" và một màn hình theo dõi trực quan ngay trên giao diện Web Admin.

**Cải tiến mới (V2.1.0):**
- Đã thêm thanh trạng thái: **"Trạng thái Auth: ✅ Đã có / ❌ Chưa có"**.
- Đã thêm nút **"🔐 Đăng nhập từ xa"**: Mở trình duyệt ảo ngay trên web để đăng nhập Google nếu token hết hạn.

---

## 2. Tư Duy Giải Quyết (The Approach)

Vì `notebooklm-mcp-auth` là một lệnh chạy trên hệ điều hành máy quét (Server), Frontend (trình duyệt Web của người dùng) **không thể** trực tiếp yêu cầu máy tính chạy lệnh đó được (vì lý do bảo mật của trình duyệt).

=> **Giải pháp:** Phải bắc cầu qua Backend.
1. **Frontend:** Có nút bấm. Khi bấm gửi một HTTP Request (API Call) xuống Backend.
2. **Backend:** Nhận Request, đóng vai trò là "người gõ phím hộ", sử dụng một thư viện đặc biệt của Python để gọi lệnh hệ điều hành chạy script kia. Sau khi lệnh chạy xong, lấy kết quả báo về cho Frontend.

---

## 3. Các Bước Thực Hiện Chi Tiết (Implementation)

### Bước 1: Sửa Backend (Tạo API "Người gõ phím hộ")
Trong file `backend_server.py`, chúng ta tạo một hàm mới hứng method `POST` tại đường dẫn `/api/admin/reauth`:

```python
import subprocess # Thư viện cốt lõi giúp Python gọi các chương trình bên ngoài

@app.post("/api/admin/reauth")
async def reauth_notebooklm(user=Depends(verify_firebase_token)):
    try:
        # Run notebooklm-mcp-auth using subprocess
        # subprocess.run sẽ làm nhiệm vụ thay ta gõ lệnh vào terminal.
        cwd = os.path.dirname(__file__) 
        process = subprocess.run(
            ["notebooklm-mcp-auth"], # Tên lệnh cần gọi
            capture_output=True,     # Lệnh này bật chế độ "Chụp lại kết quả in ra màn hình"
            text=True,               # Trả về chuỗi Text (String) thay vì Byte raw
            cwd=cwd
        )
        
        # returncode == 0 nghĩa là lệnh chạy thành công không có lỗi
        if process.returncode == 0:
            return {"status": "success", "message": "Xác thực NotebookLM thành công:\n" + process.stdout}
        else:
            return {"status": "error", "message": "Lỗi xác thực:\n" + process.stderr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```
**Bài học ở đây:** `subprocess` của Python là một "vũ khí" cực mạnh giúp ứng dụng Web của bạn tự động hóa bất kỳ phần mềm/script nào đang có trên máy chủ.

### Bước 2: Sửa Frontend (Tạo nút bấm & gọi API)
Trong file `frontend/src/App.jsx`, chúng ta thực hiện 2 việc chính:

**2.1 Khai báo biến trạng thái (State) để chặn Double-click**
Khi người dùng bấm nút, tiến trình bật Chrome lấy Cookies mất khoảng 3-5 giây. Nếu họ mất kiên nhẫn bấm liên tục, Backend sẽ chạy lệnh nhiều lần gây sập.
Ta dùng React `useState` để quản lý việc "đang tải":
```javascript
const [isReauthing, setIsReauthing] = useState(false)
```

**2.2 Viết hàm gọi API (Fetch API)**
```javascript
const handleReauth = async () => {
  setIsReauthing(true) // 1. Bật trạng thái "Đang kết nối..." làm vô hiệu hóa (disabled) nút bấm

  try {
    const response = await fetch('http://localhost:8042/api/admin/reauth', {
      method: 'POST',
      headers: { ... }
    })
    const data = await response.json() // Nhận tin nhắn từ Backend trả về
    alert(data.message)                // Pop-up thông báo hiển thị cho người dùng
  } catch (err) {
    alert('Lỗi kết nối server')
  } finally {
    setIsReauthing(false) // 3. Tắt trạng thái Loading dù thành công hay lỗi
  }
}
```

**2.3 Gắn Hàm Vào Nút Bấm Trong HTML (JSX)**
Bây giờ, thay vì code nằm trực tiếp trong `App.jsx`, chúng ta đã tách nó ra để dễ quản lý hơn. Tuy nhiên logic sử dụng vẫn tương tự:
```jsx
<button 
  onClick={handleReauth} 
  disabled={isReauthing} 
  className="save-btn"
>
  {isReauthing ? 'Đang kết nối...' : 'Kết nối lại NotebookLM'}
</button>
```
Đoạn code `{isReauthing ? 'A' : 'B'}` là toán tử ba ngôi (Ternary Operator), nếu `isReauthing` là True thì hiện chữ "Đang kết nối...", nếu False thì hiện chữ "Kết nối lại...". Còn `disabled={isReauthing}` để làm mờ cục nút, ngăn bấm.

---

## 4. Xử Lý Sự Cố Phát Sinh (Bug Fixing & Debug)

Trong quá trình thực tế cài đặt đã xuất hiện một lỗi thú vị giúp bạn học thêm về kỹ năng vận hành server:

**Lỗi xảy ra:** Cập nhật Backend xong mà giao diện bẩm nút vẫn báo lỗi `404 Not Found` (Ý bảo là API không tồn tại).
**Phân tích tình huống:**
1. Code Frontend đã trỏ đúng vào API `/api/admin/reauth`
2. Code Backend cũng đã định nghĩa API đó rõ ràng.
3. => **Tại sao lại 404?**

**Điều tra (Debug):**
- Tôi dùng lệnh Windows: `netstat -ano | findstr 8000` để xem hiện ứng dụng nào đang chiếm cổng (Port) số 8000 của server.
- Phát hiện có hẳn 2-3 tiến trình (Processes) Python đang giành nhau cổng mạng 8000. Điều này có nghĩa: Code cũ của chương trình vô hình trung bị "treo ngầm" (Zombie process) do tắt chưa chuẩn ở lần trước, nó vẫn chiếm quyền nghe request mạng đẩy tới Port 8000. Code Python mới nhất mặc dù được viết thêm API `reauth`, chạy lên nhưng **đã bị cái code cũ tranh mất lượt nhận Request**.

**Cách xử lý (Workaround):**
Đáng lẽ sẽ đi "kill" (giết) sạch các process bị kẹt, nhưng để ứng dụng hoạt động ngay và triệt để nhất, chúng ta đổi luôn cổng mạng thành **8042**. Cả khu Backend và phần Frontend gọi Endpoint đều cập nhật sang đường dẫn `http://localhost:8042/...`. 

Lúc này, ứng dụng Backend mới sẽ chạy độc quyền lập tức trên luồng 8042 hoàn toàn sạch sẽ. Và tính năng hoạt động ngon lành ngay lập tức!

---
*Hy vọng tài liệu này giúp bạn hiểu tường tận cấu trúc và xử lý logic cho ứng dụng Fullstack của mình!*
