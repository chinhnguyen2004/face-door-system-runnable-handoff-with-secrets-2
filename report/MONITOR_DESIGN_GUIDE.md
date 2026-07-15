# Hướng dẫn Thiết kế Giao diện Giám sát Face Door Monitor (`monitor.html`)

Tài liệu này hướng dẫn chi tiết các bước thiết kế và xây dựng giao diện Web Dashboard giám sát thời gian thực cao cấp sử dụng các công nghệ Web thuần (Vanilla CSS & JavaScript) và kết nối Firebase Realtime Database.

---

## 1. Thiết kế Hệ thống Màu sắc & Giao diện (Design System & Aesthetics)

Giao diện áp dụng phong cách thiết kế **Glassmorphism** trên nền tối (Dark Mode) để tạo cảm giác hiện đại và cao cấp.

### Các biến CSS chủ đạo (`:root`):
```css
:root {
  --bg-gradient: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0f0c29 50%, #03001e 100%);
  --glass-bg: rgba(17, 24, 39, 0.65);
  --glass-border: rgba(255, 255, 255, 0.08);
  --glow-green: 0 0 20px rgba(34, 197, 94, 0.4);
  --glow-red: 0 0 20px rgba(239, 68, 68, 0.4);
  --glow-blue: 0 0 25px rgba(59, 130, 246, 0.35);
  --text-main: #f3f4f6;
  --text-muted: #9ca3af;
  --accent-green: #22c55e;
  --accent-red: #ef4444;
  --accent-blue: #3b82f6;
}
```

---

## 2. Bố cục Cấu trúc HTML (Semantic Structure)

Trang web sử dụng bố cục dạng Grid hai cột (Grid Layout) để tối ưu không gian hiển thị trên màn hình máy tính và thiết bị di động:

```html
<div class="container">
  <header>
    <!-- Logo và cờ trạng thái kết nối Firebase -->
  </header>

  <div class="dashboard-grid">
    <!-- Cột trái: Thông tin nhận diện mới nhất + Trạng thái phần cứng -->
    <div class="left-column">
      <!-- Thẻ Nhận diện mới nhất -->
      <!-- Lưới 4 Thẻ Trạng thái con (Cửa, Khoảng cách Sonar, Trạng thái PC, Nhịp tim ESP) -->
    </div>

    <!-- Cột phải: Nhật ký lịch sử vào cửa thời gian thực -->
    <div class="right-column">
      <!-- Thẻ Nhật ký lịch sử cuộn tự động (Real-time Timeline) -->
    </div>
  </div>
</div>
```

---

## 3. Tạo hiệu ứng kính mờ (Glassmorphism) & Hiệu ứng chuyển động (Micro-animations)

### Hiệu ứng Kính mờ:
Sử dụng bộ lọc làm mờ phông nền phía sau thẻ card kết hợp đường viền nửa trong suốt:
```css
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--glass-border);
  border-radius: 20px;
}
```

### Hiệu ứng Chuyển động (Micro-animations):
1. **Nháy xanh trạng thái kết nối (`@keyframes pulse`):** Làm cho chấm tròn trạng thái online nhấp nháy êm dịu.
2. **Nhật ký đẩy vào (`@keyframes slideIn`):** Mỗi khi có bản ghi lịch sử mới xuất hiện, nó sẽ trượt nhẹ từ dưới lên và mờ dần sang rõ nét.
3. **Hiệu ứng phát sáng hồ sơ (`profile-glow`):** Một vầng sáng màu xanh (Thành công) hoặc đỏ (Người lạ) ẩn dưới ảnh đại diện, lan tỏa êm ái bằng thuộc tính `filter: blur(40px)`.

---

## 4. Kết nối Firebase Realtime Database qua JavaScript

Sử dụng thư viện SDK tương thích ngược (Compat version) tải từ CDN để kết nối cơ sở dữ liệu:

```javascript
const firebaseConfig = {
  apiKey: "AIzaSyCIhDZJHgZYMhu_PkccpoHbMNp1bSZ65EE",
  authDomain: "face-f49c1.firebaseapp.com",
  databaseURL: "https://face-f49c1-default-rtdb.asia-southeast1.firebasedatabase.app/",
  projectId: "face-f49c1"
};

firebase.initializeApp(firebaseConfig);
const database = firebase.database();
```

---

## 5. Đồng bộ và cập nhật dữ liệu trực quan (Real-time DOM Data Sync)

### 5.1. Đồng bộ kết nối:
Lắng nghe nút `.info/connected` để đổi màu cờ trạng thái kết nối mạng:
```javascript
database.ref(".info/connected").on("value", (snapshot) => {
  // Thay đổi class sang online (xanh lá) hoặc offline (đỏ)
});
```

### 5.2. Đồng bộ kết quả nhận dạng:
Lắng nghe đường dẫn `/recognitions/esp01` để cập nhật tên người vào, mã sinh viên, độ tin cậy và mốc thời gian:
* Nếu là `"Unknown"`, áp dụng class `.fail-border` để làm viền đỏ và hiển thị icon cảnh báo `🚨`.
* Nếu là tên người quen, áp dụng class `.success-border` làm viền xanh lá và hiển thị icon tốt nghiệp `🎓`.

### 5.3. Đồng bộ phần cứng cửa và cảm biến:
* **Khóa cửa:** Lắng nghe `/status/esp01/doorOpen` để cập nhật icon `🔓` (Đang mở) hoặc `🔒` (Đang đóng).
* **Cảm biến siêu âm:** Lắng nghe `/status/esp01/distance_cm` để cập nhật số cm hiển thị và tự động tính toán % độ rộng thanh trượt tiến trình (`progressFill.style.width = percent%`).
* **Heartbeat:** Lắng nghe `/status/esp01/lastSeenMs` để quy đổi thời gian hoạt động liên tục (uptime) của ESP8266 ra định dạng phút, giây.

### 5.4. Đồng bộ Nhật ký vào cửa:
Lắng nghe nút `/history` giới hạn **12 phần tử gần nhất** (`limitToLast(12)`). Mỗi khi có dữ liệu thay đổi, dùng vòng lặp `forEach` để tạo các phần tử HTML động dạng danh sách dòng thời gian (Timeline) và đẩy lên giao diện.
