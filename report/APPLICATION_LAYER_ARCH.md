# Các Giao thức và Kiến trúc Lớp Ứng dụng của Giao diện Giám sát `facedoormonitor`

Tài liệu này phân tích chi tiết cấu trúc kiến trúc phần mềm và các giao thức truyền thông ở **Lớp ứng dụng (Application Layer)** được áp dụng để phát triển giao diện giám sát thời gian thực cao cấp [monitor.html](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/monitor.html).

---

## 1. Kiến trúc Phần mềm ở Lớp Ứng dụng (Software Architecture)

Giao diện giám sát áp dụng các mô hình kiến trúc phần mềm hiện đại nhằm đảm bảo hiệu năng thời gian thực và trải nghiệm người dùng mượt mà:

### 1.1. Kiến trúc Hướng Sự kiện (Event-Driven Architecture - EDA)
Thay vì sử dụng cơ chế kéo dữ liệu truyền thống (HTTP Pulling / Polling) gây lãng phí tài nguyên và tạo độ trễ lớn, `monitor.html` hoạt động hoàn toàn theo mô hình **Publish-Subscribe (Pub/Sub)**:
* **Publishers:** Mạch ESP8266 (đẩy khoảng cách sonar, trạng thái cửa) và Server Python (đẩy kết quả nhận diện khuôn mặt) lên Firebase.
* **Broker:** Đám mây Firebase Realtime Database quản lý trạng thái dữ liệu tập trung.
* **Subscriber:** Trình duyệt web (`monitor.html`) đăng ký lắng nghe sự kiện thay đổi dữ liệu trên các nút đích thông qua các hàm callback:
  ```javascript
  database.ref("/recognitions/esp01").on("value", (snapshot) => { ... });
  ```
  Ngay khi dữ liệu trên Firebase thay đổi, Broker sẽ chủ động đẩy (Push) gói tin chứa dữ liệu mới nhất về trình duyệt để cập nhật giao diện ngay lập tức.

### 1.2. Kiến trúc Render phía Khách (Client-Side Rendering - CSR)
* Trang web hoạt động như một ứng dụng đơn trang (Single Page Application - SPA) thu nhỏ. 
* Toàn bộ cấu trúc giao diện tĩnh (HTML/CSS) được trình duyệt tải và dựng một lần duy nhất.
* Mọi cập nhật dữ liệu thời gian thực sau đó được thực hiện động qua JavaScript (DOM Manipulation) mà không cần tải lại toàn bộ trang web, giúp tối ưu hóa băng thông mạng và loại bỏ hiện tượng giật màn hình.

---

## 2. Các Giao thức Lớp Ứng dụng (Application Layer Protocols)

Giao diện Web sử dụng kết hợp các giao thức mạng phổ biến để tải tài nguyên và truyền dẫn luồng dữ liệu bảo mật:

### 2.1. Giao thức WebSockets \& Server-Sent Events (SSE)
* **Ứng dụng:** Đồng bộ cơ sở dữ liệu thời gian thực giữa Firebase Database và trình duyệt.
* **Cách hoạt động:** Firebase Client SDK thiết lập một kênh kết nối song công (Bidirectional Duplex Connection) duy nhất thông qua giao thức **WebSockets** (hoặc tự động chuyển về **Server-Sent Events - SSE** / **HTTP Long Polling** nếu cổng truyền tin bị tường lửa chặn). Kênh truyền tin này giúp bỏ qua bước bắt tay (handshake) TCP/TLS phiền phức của từng lệnh đọc, giảm độ trễ phản hồi xuống dưới **`100ms`**.

### 2.2. Giao thức HTTPS (Hypertext Transfer Protocol Secure)
* **Ứng dụng:** Truy cập trang web, tải các thư viện tĩnh CDN (Firebase SDK, Google Fonts) và là phương thức bảo mật truyền tin cơ bản.
* **Mã hóa bảo mật:** Toàn bộ dữ liệu trao đổi được mã hóa qua giao thức lớp bảo mật **TLS 1.2/1.3** trên cổng bảo mật chuẩn `443`. Điều này ngăn chặn hoàn toàn việc rò rỉ hình ảnh nhận dạng, mã sinh viên hay mã khóa token bí mật (`DATABASE_SECRET`) trên đường truyền Internet công cộng.

### 2.3. Giao thức Định dạng Dữ liệu JSON (JavaScript Object Notation)
* **Ứng dụng:** Là chuẩn định dạng dữ liệu (Payload Format) cho mọi gói tin trao đổi ở lớp ứng dụng.
* **Ưu điểm:** JSON là chuẩn định dạng cực kỳ nhẹ, tối giản ký tự, dễ đọc bởi cả con người và máy tính. Nó giúp chuyển đổi các đối tượng dữ liệu phức tạp (như danh sách hồ sơ học sinh, lịch sử ra vào kèm ảnh mốc thời gian) thành các chuỗi văn bản tinh gọn để truyền dẫn qua mạng Internet một cách nhanh nhất.
