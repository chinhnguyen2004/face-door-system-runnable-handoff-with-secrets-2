# Bộ Câu Hỏi & Trả Lời Phản Biện Dành Cho Giám Khảo Khó Tính

Tài liệu này tổng hợp các câu hỏi hóc búa nhất mà Hội đồng giám khảo hoặc giảng viên phản biện có thể đặt ra cho 3 phân lớp của đồ án: **Lớp Cảm nhận**, **Lớp Mạng** và **Lớp Ứng dụng**. Kèm theo đó là các câu trả lời chuẩn kỹ thuật, dựa trên thực tế mã nguồn và kiến trúc hệ thống đã tối ưu.

---

## PHẦN 1: THIẾT KẾ VÀ TRIỂN KHAI LỚP CẢM NHẬN

### Câu 1: Tại sao em lại lựa chọn ESP8266 thay vì ESP32 cho hệ thống này? ESP32 mạnh hơn nhiều và có camera tích hợp (ESP32-CAM) tại sao không dùng để giảm bớt máy tính (PC)?
* **Trả lời phản biện:**
  1. **Về hiệu năng AI:** Mô hình nhận diện khuôn mặt học sâu (YuNet + SFace) yêu cầu năng lực tính toán dấu phẩy động rất lớn để trích xuất vector đặc trưng 128 chiều thời gian thực. ESP32 hay ESP32-CAM có RAM rất hạn chế ($\approx 520\text{ KB}$) và CPU tốc độ thấp ($240\text{ MHz}$), không thể chạy mô hình AI lớn như SFace với tốc độ khung hình cao (FPS sẽ dưới 1 hình/giây và gây trễ cực nặng).
  2. **Giải pháp phân tán:** Hệ thống chọn kiến trúc biên phối hợp máy chủ. ESP8266 làm vi điều khiển biên (Edge node) giá thành rẻ, tối ưu tốt cho việc đọc cảm biến và điều khiển cơ cấu chấp hành (Servo). PC đóng vai trò máy chủ xử lý tác vụ AI nặng.
  3. **Lý do chọn ESP8266:** Đạt hiệu quả tối ưu về giá thành phần cứng và đủ đáp ứng các yêu cầu xử lý logic tại biên của mô hình khóa cửa.

### Câu 2: Tôi thấy trong code em dùng cơ chế `attach()` và `detach()` liên tục cho Servo. Tại sao không `attach()` một lần ở `setup()` rồi dùng mãi? Cách làm của em có tác dụng gì và nhược điểm là gì?
* **Trả lời phản biện:**
  * **Lý do:** ESP8266 không có bộ điều khiển PWM bằng phần cứng chuyên dụng cho Servo mà phải mô phỏng bằng phần mềm (Software PWM thông qua ngắt ngầm). Khi chip thực hiện kết nối mạng Wi-Fi và mã hóa HTTPS (SSL BearSSL), các ngắt mạng ưu tiên cao sẽ chặn ngắt phần mềm của Servo, gây méo dạng xung điều khiển khiến Servo bị **rung giật liên tục (jitter)** gây nóng máy, hỏng nhông và tốn điện. Cơ chế `attach()` khi quay và `detach()` ngay sau 600ms giúp tắt hẳn xung điều khiển khi Servo đứng yên, giải phóng tài nguyên CPU và **triệt tiêu hoàn toàn rung lắc**.
  * **Nhược điểm:** Khi đã `detach()`, Servo sẽ không còn lực giữ (holding torque). Tuy nhiên với khóa cửa chốt, lực giữ tĩnh của cơ cấu cơ khí là đủ, không cần động cơ phải ghì lực liên tục.

### Câu 3: Cảm biến siêu âm HC-SR04 rất hay bị nhiễu do sóng phản xạ hoặc môi trường, làm cách nào hệ thống của em không bị kích hoạt nhầm hoặc tự động hủy quét?
* **Trả lời phản biện:**
  Hệ thống đã triển khai bộ lọc nhiễu **Software Debouncing Filter** tại firmware biên:
  1. Tần suất đọc cảm biến được đẩy nhanh lên **`300ms/lần`**.
  2. Sử dụng bộ đếm tích lũy `consecutiveOutCount`: Chỉ khi cảm biến đo được khoảng cách ngoài vùng kích hoạt ($> 50\text{ cm}$) liên tục **`5 lần` (khoảng 1.5 giây)** thì hệ thống mới xác nhận người dùng đã đi khỏi và hủy yêu cầu quét. 
  3. Mọi xung nhiễu đơn lẻ nhảy vọt (ví dụ đột ngột nhảy lên 90cm rồi quay lại 15cm) sẽ bị bộ đếm phát hiện và lập tức reset về 0, đảm bảo camera không bị bật/tắt chập chờn.

---

## PHẦN 2: THIẾT KẾ VÀ TRIỂN KHAI LỚP MẠNG

### Câu 1: Em đang sử dụng Database Secret (Legacy Token) để xác thực Firebase trên Python. Google đã thông báo lỗi thời (deprecated) cơ chế này. Tại sao em không dùng Service Account JSON (`admin_firebase.json`) theo chuẩn hiện đại?
* **Trả lời phản biện:**
  * **Bảo mật mã nguồn mở:** Khi đưa dự án lên kho lưu trữ công khai (Public GitHub) để cộng đồng dễ dàng tiếp cận, Google Cloud quét tự động sẽ lập tức thu hồi và vô hiệu hóa khoá tài khoản dịch vụ (`admin_firebase.json`) trong vòng vài giây để bảo vệ tài khoản chống khai thác trái phép.
  * **Giải pháp thích ứng:** Để hệ thống hoạt động ổn định trên repo công khai mà không bị quét khóa tự động từ Google, cơ chế **REST API** kết hợp **Database Secret** là giải pháp tối ưu. Mã này được giới hạn quyền chỉ đọc/ghi cơ sở dữ liệu thời gian thực được chỉ định và hoạt động độc lập với hệ thống quản lý tài khoản dịch vụ GCP, giúp đảm bảo tính khả dụng của đồ án.

### Câu 2: Kết nối SSL (BearSSL) trên ESP8266 tiêu tốn rất nhiều RAM (khoảng 20-30 KB cho handshake). Làm thế nào em đảm bảo ESP8266 không bị tràn RAM (Out of Memory) dẫn đến sập kết nối khi chạy lâu dài?
* **Trả lời phản biện:**
  1. Sử dụng phương thức thiết lập giới hạn cứng kích hoạt bộ đệm phản hồi của Firebase:
     ```cpp
     fbdo.setResponseSize(512);
     ```
     Lệnh này giới hạn bộ đệm phản hồi tối đa là 512 bytes thay vì mặc định 1024-2048 bytes, tiết kiệm tài nguyên bộ nhớ Heap quý giá.
  2. Sử dụng kết nối HTTPS không xác thực chứng chỉ toàn diện (`client->setInsecure()`) để bỏ qua bước lưu trữ chuỗi chứng chỉ SSL CA cồng kềnh trong bộ nhớ flash/RAM của vi điều khiển.

### Câu 3: Độ trễ phản hồi từ lúc quét mặt trên PC đến lúc cửa mở là bao nhiêu? Em đã làm gì để tối ưu hóa thời gian này?
* **Trả lời phản biện:**
  Độ trễ phản hồi thực tế hiện tại là **dưới 0.5 giây**. Để đạt được con số này, hệ thống đã tối ưu:
  1. **Quét dữ liệu động (Dynamic Polling):** Mạch ESP8266 bình thường sẽ chạy chậm ở chu kỳ 2.5 giây để tiết kiệm băng thông. Nhưng ngay khi có người đứng trước cảm biến, mạch chuyển sang chu kỳ quét siêu nhanh **`150ms`**.
  2. **Tối ưu hóa số lượng yêu cầu (Request reduction):** Chỉ truy vấn đúng tệp timestamp kiểm tra thay đổi (`getString(resultTimePath)`). Khi phát hiện mốc thời gian thay đổi, mạch mới gọi tiếp lệnh đọc tên nhận diện, giúp giảm thiểu số lượng cuộc gọi mạng API không cần thiết.

---

## PHẦN 3: THIẾT KẾ VÀ TRIỂN KHAI LỚP ỨNG DỤNG

### Câu 1: Tại sao em lại chọn mô hình YuNet và SFace mà không phải là Haar Cascades + LBPH (truyền thống) hay FaceNet?
* **Trả lời phản biện:**
  1. **So với Haar Cascades + LBPH:** Mô hình truyền thống rất nhạy cảm với ánh sáng, góc nghiêng khuôn mặt và tỷ lệ nhận diện sai cực kỳ cao trong thực tế. YuNet (mạng CNN nhẹ) và SFace (mạng học sâu tối ưu hóa) cho độ chính xác vượt trội, nhận diện tốt kể cả khi đeo khẩu trang một phần hoặc mặt bị nghiêng góc lớn.
  2. **So với FaceNet:** FaceNet yêu cầu tài nguyên phần cứng lớn, chạy nặng trên CPU thường không card đồ họa. Bộ đôi YuNet và SFace được OpenCV tối ưu trực tiếp cho mô-đun DNN, chạy cực kỳ nhẹ trên các máy chủ PC phổ thông hoặc thiết bị nhúng (FPS đạt từ 15-30 khung hình/giây trên CPU).

### Câu 2: Trong thực tế, mô hình nhận diện khuôn mặt dễ bị đánh lừa bằng một bức ảnh chân dung trên điện thoại di động. Hệ thống của em có giải pháp nào để chống lại hình thức tấn công giả mạo này (Anti-spoofing)?
* **Trả lời phản biện:**
  * **Thực trạng hiện tại:** Đồ án tập trung nghiên cứu triển khai luồng xử lý AI cơ bản và tối ưu hóa hệ thống IoT thời gian thực, do đó hiện tại chưa tích hợp các cảm biến chuyên dụng chống giả mạo như Camera chiều sâu (Depth Camera - RealSense) hoặc cảm biến hồng ngoại (IR).
  * **Giải pháp phần mềm hướng nâng cấp:** Hệ thống hoàn toàn có thể nâng cấp thuật toán bằng cách tích hợp tính năng **phát hiện chớp mắt (Liveness Detection)** dựa trên 5 điểm mốc khuôn mặt mà YuNet trả về hoặc yêu cầu người dùng quay nhẹ đầu để kiểm tra chuyển động 3D của các điểm mốc trước khi cho phép đối sánh SFace.

### Câu 3: Giao diện facedoormonitor sử dụng công nghệ gì? Nếu mất mạng Internet thì giao diện có hoạt động được không?
* **Trả lời phản biện:**
  * **Công nghệ:** Giao diện sử dụng HTML5, Vanilla CSS3 (cho phong cách Glassmorphism, Responsive Grid và các vi chuyển động mượt mà) cùng JavaScript thuần kết nối trực tiếp tới Firebase qua giao thức WebSockets.
  * **Khả năng ngoại tuyến (Offline):** Do giao diện phụ thuộc hoàn toàn vào dịch vụ đám mây Firebase Realtime Database làm cầu nối dữ liệu, nếu mất mạng Internet ngoài, luồng đẩy dữ liệu thời gian thực giữa PC $\rightarrow$ Firebase $\rightarrow$ Web Dashboard sẽ bị gián đoạn. Tuy nhiên, hệ thống có thể chuyển đổi cấu trúc sang mạng LAN cục bộ bằng cách triển khai một REST Server mini chạy Python ngay trên PC và mạch ESP8266 sẽ kết nối trực tiếp đến IP của PC thông qua mạng Wi-Fi nội bộ.
