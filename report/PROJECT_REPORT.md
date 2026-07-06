# BÁO CÁO DỰ ÁN: HỆ THỐNG CỬA TỰ ĐỘNG NHẬN DIỆN KHUÔN MẶT (AI FACE DOOR SYSTEM)

Dự án phát triển hệ thống khóa cửa thông minh tích hợp nhận diện khuôn mặt thời gian thực sử dụng trí tuệ nhân tạo (mô hình mạng học sâu YuNet + SFace), truyền thông qua cơ sở dữ liệu đám mây Firebase Realtime Database, thông báo qua Discord Webhook và điều khiển phần cứng bằng vi điều khiển ESP8266 NodeMCU.

---

## 1. THÀNH PHẦN HỆ THỐNG

### 1.1. Sơ đồ kết nối phần cứng (Hardware Wiring)
Hệ thống sử dụng board vi điều khiển **ESP8266 NodeMCU Lolin v3** cắm trên Breadboard kết nối với các linh kiện ngoại vi sau:

| Thiết bị / Linh kiện | Chân trên ESP8266 | Vai trò trong hệ thống |
| :--- | :--- | :--- |
| **Cảm biến siêu âm** | `TRIG` -> `D5` (GPIO14)<br>`ECHO` -> `D6` (GPIO12) | Đo khoảng cách phát hiện có người đứng trước cửa ($<50\text{ cm}$) để kích hoạt camera. |
| **Động cơ Servo (SG90/MG90S)** | `Signal` -> `D0` (GPIO16) | Đóng/mở chốt khóa cửa cơ khí. |
| **Màn hình LCD 16x2 (I2C)** | `SCL` -> `D1` (GPIO5)<br>`SDA` -> `D2` (GPIO4) | Hiển thị trạng thái hoạt động trực quan cho người dùng. |
| **LED Thành công (Đèn xanh)** | `Anode` -> `D3` (GPIO0) | Sáng khi nhận diện đúng sinh viên đã đăng ký trong hệ thống. |
| **LED Thất bại (Đèn đỏ)** | `Anode` -> `D4` (GPIO2) | Sáng khi phát hiện người lạ (Unknown) hoặc nhận diện thất bại. |

---

## 2. KIẾN TRÚC PHẦN MỀM & ĐƯỜNG TRUYỀN DỮ LIỆU (DATAFLOW)

Hệ thống hoạt động dựa trên sự phối hợp nhịp nhàng giữa **Mạch điều khiển (ESP8266)** và **Chương trình xử lý AI (PC Python)** thông qua **Firebase Realtime Database**:

```
[ Cảm biến siêu âm ]
        │ (Khoảng cách < 50cm)
        ▼
[ Mạch ESP8266 ] ────(ghi /capture_request = true)───► [ Firebase RTDB ]
                                                             │
                                                             │ (nhận cờ kích hoạt)
                                                             ▼
[ Đèn LED D3 / D4 ] ◄──(nhận diện xong & mở khóa)── [ PC Python (YuNet + SFace) ]
                                                             │
                                                             ▼
                                                    [ Discord Webhook ] (Gửi alert)
```

---

## 3. CÁC ĐIỂM CẢI TIẾN CÔNG NGHỆ CHỦ CHỐT (KEY OPTIMIZATIONS)

### 3.1. Nâng cấp bộ nhận diện AI (YuNet + SFace Deep Learning)
* **Trước đây:** Sử dụng Haar Cascade (phát hiện mặt chậm, dễ bắt nhầm) và LBPH (độ chính xác thấp, nhạy cảm với ánh sáng, file model `.xml` nặng tới 161 MB).
* **Hiện tại:** Sử dụng pipeline học sâu của OpenCV:
  * **YuNet:** Phát hiện khuôn mặt siêu nhanh, hỗ trợ góc nghiêng tốt, hoạt động bền bỉ trong môi trường thiếu sáng.
  * **SFace:** Trích xuất đặc trưng khuôn mặt thành vector 128 chiều, so sánh bằng khoảng cách Cosine (Cosine Similarity).
  * **Cơ sở dữ liệu:** Lưu trữ dưới dạng file JSON nhẹ chỉ **3 KB** ([models/embeddings.json](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/models/embeddings.json)), dễ dàng đồng bộ và bảo trì. Ngưỡng nhận diện tối ưu thiết lập ở mức **`0.36`**.

### 3.2. Khắc phục lỗi kết nối SSL (RAM Optimization on ESP8266)
* **Vấn đề:** Do chip ESP8266 có dung lượng RAM rất hạn chế (khoảng 80KB), kết nối bảo mật **BearSSL (HTTPS)** của Firebase thường bị sập giữa chừng với lỗi `Failed to initialize the SSL layer` do tràn bộ nhớ (Out of Memory).
* **Giải pháp:** Giới hạn dung lượng đệm phản hồi của Firebase trong code Arduino xuống còn `512` byte:
  ```cpp
  fbdo.setResponseSize(512);
  ```
  Giúp tiết kiệm bộ nhớ tối đa, giữ kết nối SSL của mạch luôn ổn định 24/7.

### 3.3. Loại bỏ nhiễu và triệt tiêu Servo tự quay (Dynamic Attach/Detach)
* **Vấn đề:** Thư viện `Servo` trên ESP8266 tạo xung PWM bằng phần mềm. Khi mạch bận xử lý mã hóa SSL hoặc truyền Wi-Fi, xung PWM bị méo làm động cơ servo bị rung, giật hoặc tự động quay tròn liên tục.
* **Giải pháp:** Áp dụng cơ chế **Cấp/Ngắt nguồn động cơ động**:
  * Chỉ kết nối chân điều khiển Servo (`attach()`) khi cần xoay mở hoặc đóng cửa.
  * Rút kết nối (`detach()`) ngay sau khi động cơ quay xong (0.6 giây delay).
  ```cpp
  doorServo.attach(SERVO_PIN);
  doorServo.write(SERVO_OPEN_DEG);
  delay(600);
  doorServo.detach(); // Động cơ đứng im tuyệt đối sau khi quay
  ```

### 3.4. Cơ chế Biểu quyết đa khung hình ở chế độ Độc lập (Multi-frame Standalone Voting)
* **Vấn đề:** Ở chế độ camera mở liên tục (Standalone), nếu nhận diện chỉ bằng 1 khung hình đơn lẻ, hệ thống rất dễ bị nhiễu động hoặc nhận diện nhầm khi người dùng vừa bước tới (mặt bị nhòe).
* **Giải pháp:** Thiết lập bộ tích lũy biểu quyết **5 khung hình**:
  * Camera chụp liên tục các khung hình có mặt.
  * Khi thu thập đủ **5 khung hình**, hệ thống tiến hành biểu quyết đa số thắng thiểu số để chọn ra nhãn nhận diện cuối cùng (Người quen hoặc Unknown).
  * Nếu camera không thấy mặt quá 2 giây, bộ nhớ đệm tự động reset về 0 để tránh cộng dồn nhầm với người tiếp theo.
  * Sau khi gửi kết quả, hệ thống bật chế độ chờ (cooldown) 5 giây rồi mới kích hoạt lượt quét mới.

---

## 4. HƯỚNG DẪN VẬN HÀNH HỆ THỐNG

### 4.1. Cách nạp code và chạy mạch phần cứng
1. Mở phần mềm **Arduino IDE**.
2. Mở file chính: [integrated_firebase_door.ino](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/temp/integrated_firebase_door/integrated_firebase_door.ino).
3. Đảm bảo file [secrets.h](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/temp/integrated_firebase_door/secrets.h) đã khai báo đúng tên Wi-Fi và mật khẩu của bạn:
   ```cpp
   #define WIFI_SSID "P2205"
   #define WIFI_PASSWORD "66668888"
   ```
4. Chọn Board **`NodeMCU 1.0 (ESP-12E Module)`** và cổng kết nối tương ứng (ví dụ: **`COM4`**).
5. Nhấn **Upload** để nạp code.

*Lưu ý: Nếu muốn kiểm tra hoạt động của 2 đèn LED độc lập để xác nhận đường dây trên Breadboard đấu nối chính xác, bạn có thể nạp file test [led_test.ino](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/temp/led_test/led_test.ino) trước.*

### 4.2. Khởi chạy hệ thống nhận diện AI trên PC
Mở thư mục dự án và chạy file script **`run_face_listener_discord.cmd`**:
* **Lựa chọn 1 (Start Main Listener):** Mở camera trên PC ở chế độ hoạt động liên tục (Standalone). Bạn chỉ cần đứng trước camera, hệ thống tự động tích lũy đủ 5 khung hình tốt nhất để nhận diện, mở cửa qua Firebase và gửi cảnh báo ảnh/tin nhắn kèm mã sinh viên về Discord Webhook.
* **Lựa chọn 2 (Capture New Face):** Đăng ký thêm khuôn mặt mới vào hệ thống (Nhập MSV và Tên tiếng Việt không dấu).
* **Lựa chọn 3 (Train Model):** Chạy huấn luyện để trích xuất đặc trưng khuôn mặt mới đăng ký và cập nhật vào cơ sở dữ liệu embeddings JSON.
* **Lựa chọn 4 (Test Webcam):** Chạy thử nghiệm khung hình camera cục bộ để xem điểm tương đồng Cosine.
