# Bộ Câu Hỏi & Trả Lời Phản Biện Dành Cho Giám Khảo Khó Tính (Bản Đầy Đủ)

Tài liệu này tổng hợp 18 câu hỏi hóc búa nhất (6 câu hỏi cho mỗi phân lớp) mà Hội đồng giám khảo hoặc giảng viên phản biện có thể đặt ra cho đồ án: **Lớp Cảm nhận**, **Lớp Mạng** và **Lớp Ứng dụng**. Kèm theo đó là các câu trả lời chuẩn kỹ thuật, dựa trên thực tế mã nguồn và kiến trúc hệ thống đã tối ưu.

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

### Câu 4: Tại sao em cấu hình chân LED trắng ở D4 và LED đỏ ở D3? Các chân D3 (GPIO0) và D4 (GPIO2) của ESP8266 là các chân boot strapping (quyết định chế độ khởi động), nếu kết nối phần cứng sai có ảnh hưởng gì không?
* **Trả lời phản biện:**
  * Chân **GPIO0 (D3)** và **GPIO2 (D4)** là các chân boot strapping của ESP8266. Khi khởi động nguồn (boot), chip yêu cầu chân GPIO0 phải ở mức `HIGH` để vào chế độ chạy chương trình bình thường (Normal Boot). Nếu chân này bị kéo xuống mức `LOW` (ví dụ do đấu đèn LED trực tiếp xuống đất không có trở hạn dòng lớn để ghim áp), ESP8266 sẽ tự động chuyển sang chế độ nạp flash (Flash Mode) và bị treo máy, không chạy chương trình.
  * **Giải pháp khắc phục:** Trong mạch của em, các đèn LED được kết nối nối tiếp với điện trở hạn dòng đủ lớn ($220\,\Omega - 330\,\Omega$) và được cấu hình xuất tín hiệu phù hợp để không làm ảnh hưởng đến điện áp phân cực logic của các chân này trong quá trình khởi động.

### Câu 5: Cảm biến siêu âm HC-SR04 đo khoảng cách bằng cách nào? Trong code em cấu hình `ECHO_TIMEOUT_US = 30000UL` (30ms). Con số này có ý nghĩa gì và ảnh hưởng thế nào đến giới hạn khoảng cách đo?
* **Trả lời phản biện:**
  * **Nguyên lý:** Cảm biến siêu âm đo khoảng cách bằng phương pháp thời gian bay (Time-of-Flight). Nó phát ra 1 chùm sóng siêu âm ngắn, sóng đập vào vật cản dội lại chân Echo. Khoảng cách được tính bằng công thức: $S = t \times 0.034 / 2$ (với $t$ tính bằng micro-giây, vận tốc âm thanh $\approx 0.034\text{ cm/\mu s}$).
  * **Ý nghĩa Timeout:** `ECHO_TIMEOUT_US = 30000` (30ms) giới hạn thời gian chờ tối đa phản xạ sóng Echo. Khoảng cách tối đa đo được tương ứng là: $30000 / 58 \approx 517\text{ cm}$ ($\approx 5.1\text{ mét}$). Cấu hình này giúp ngăn ngừa việc vi điều khiển bị đứng/treo vô hạn ở hàm `pulseIn()` khi chùm sóng phát đi mà không gặp vật cản để phản xạ lại (vùng trống trải rộng lớn), giúp luồng chương trình chạy mượt mà.

### Câu 6: Động cơ servo MG90S hoạt động dựa trên nguyên lý nào? Tần số và độ rộng xung điều khiển (PWM) là bao nhiêu? Nếu chốt khóa cửa cơ khí bị kẹt cứng, điều gì sẽ xảy ra?
* **Trả lời phản biện:**
  * **Nguyên lý:** Servo hoạt động bằng xung điều khiển PWM với chu kỳ tiêu chuẩn là $20\text{ ms}$ (tần số $50\text{ Hz}$). Góc quay của Servo từ $0^\circ$ đến $180^\circ$ tương ứng với độ rộng xung ở mức `HIGH` dao động từ $0.5\text{ ms}$ (500us) đến $2.5\text{ ms}$ (2500us).
  * **Trường hợp bị kẹt cứng cơ khí:** Servo sẽ liên tục cố ghì để đạt tới góc đích, dòng điện tiêu thụ tăng vọt lên dòng cực hạn (Stall Current $\approx 800\text{mA} - 1\text{A}$). Dòng điện quá lớn này sẽ gây sụt áp nguồn của ESP8266 làm vi điều khiển bị reset liên tục (Brownout), hoặc gây quá nhiệt cháy cuộn dây của motor.
  * **Giải pháp bảo vệ:** Nhờ cơ chế chỉ `attach()` khi quay và lập tức `detach()` sau 600ms, hệ thống của em hoàn toàn loại bỏ nguy cơ này. Dù bị kẹt cứng cơ khí, sau 600ms dòng điện cấp cho Servo sẽ bị ngắt hoàn toàn, bảo vệ an toàn tuyệt đối cho phần cứng.

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

### Câu 4: Hệ thống sử dụng Wi-Fi chuẩn IEEE 802.11 b/g/n. Tần số hoạt động của chuẩn này là bao nhiêu? Có những nguồn gây nhiễu nào trong thực tế ảnh hưởng đến kết nối của ESP8266 và cách khắc phục?
* **Trả lời phản biện:**
  * **Tần số:** Chuần b/g/n hoạt động ở dải tần vô tuyến **`2.4 GHz`**.
  * **Nguồn gây nhiễu:** Các thiết bị Bluetooth, lò vi sóng, thiết bị gia dụng không dây hoặc sóng Wi-Fi từ các router lân cận phát trùng kênh (Channel overlap). 
  * **Giải pháp khắc phục:** 
    1. Cấu hình router phát sóng tại các kênh tần số không chồng chéo nhau (Kênh 1, 6 hoặc 11).
    2. Đặt ESP8266 ở vị trí thông thoáng, tránh xa các vật cản kim loại lớn hoặc thiết bị phát sóng mạnh.
    3. Tích hợp cơ chế tự động kết nối lại (`reconnectWiFi(true)`) của thư viện Firebase để lập tức khôi phục liên lạc khi xảy ra rớt mạng ngắn hạn.

### Câu 5: Chuyện gì xảy ra nếu Server Python xử lý AI bị mất kết nối mạng đột ngột trong khi ESP8266 đang gửi yêu cầu quét mặt? Mạch biên có bị treo ở trạng thái chờ không?
* **Trả lời phản biện:**
  * Khi Server Python mất mạng, cờ yêu cầu quét `/capture_request` trên Firebase vẫn giữ trạng thái `true` vì không có ai xóa đi.
  * Mạch ESP8266 biên **sẽ không bị treo vô hạn**. Hệ thống đã được lập trình cơ chế tự phục hồi lỗi thời gian chờ **Timeout**:
    ```cpp
    if (captureRequested && now - captureStartedMs >= RECOGNITION_TIMEOUT_MS) {
        captureRequested = false;
        Firebase.RTDB.setBool(&fbdo, capturePath.c_str(), false);
        Firebase.RTDB.setString(&fbdo, messagePath.c_str(), "Recognition timeout");
        lcdLine(0, "System ready");
        lcdLine(1, "Waiting...");
    }
    ```
    Sau tối đa `15 giây` không nhận được kết quả nhận diện mới từ Firebase, ESP8266 tự động xóa cờ yêu cầu quét, đóng chốt an toàn và trả màn hình LCD về trạng thái sẵn sàng đón người tiếp theo.

### Câu 6: Tại sao em lại thiết kế gửi thông báo Discord Webhook từ PC (Server Python) chứ không gửi trực tiếp từ mạch ESP8266 để tăng tính độc lập của thiết bị IoT?
* **Trả lời phản biện:**
  1. **Hạn chế phần cứng:** Mạch ESP8266 có bộ nhớ RAM và năng lực CPU rất hạn chế. Để gửi thông báo Discord, mạch cần thiết lập thêm 1 luồng HTTPS SSL bắt tay mã hóa phức tạp và biên dịch chuỗi JSON payload cồng kềnh (Rich Embed). Việc này sẽ làm mạch cạn kiệt RAM và gây trễ cực kỳ nặng cho tác vụ điều khiển chốt khóa cửa chính.
  2. **Hiệu năng xử lý:** PC có tài nguyên dồi dào, hỗ trợ xử lý đa luồng (Multi-threading). Việc gửi thông báo Discord được thực hiện bất đồng bộ trên PC giúp thông báo được gửi đi ngay lập tức mà hoàn toàn không ảnh hưởng đến hoạt động cơ khí tức thời của khóa cửa.

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

### Câu 4: Thuật toán biểu quyết đa khung hình (Multi-frame Voting) hoạt động như thế nào trong chế độ Standalone? Tại sao em cần đặt thời gian timeout là 2.0 giây để reset bộ đếm khi không thấy mặt?
* **Nguyên lý hoạt động:** Ở chế độ Standalone, hệ thống liên tục phân tích và đối sánh từng khung hình đơn lẻ. Kết quả nhận diện (Tên, Mã SV hoặc Unknown) của mỗi khung hình được đẩy vào một hàng đợi (tối đa 5 phần tử). Khi hàng đợi đủ 5 mẫu, thuật toán lấy nhãn xuất hiện nhiều nhất (Majority vote) làm kết quả cuối cùng.
* **Lý do cần Timeout 2.0s:** Khi một người vừa quét xong đi ra, hàng đợi có thể còn sót lại 2-3 khung hình tích lũy dở dang của họ. Nếu người tiếp theo bước vào lập tức, các khung hình của hai người sẽ bị trộn lẫn dẫn đến nhận diện sai lệch. Bộ đếm thời gian 2.0 giây sẽ tự động dọn sạch (clear) hàng đợi nếu camera không phát hiện thấy bất kỳ khuôn mặt nào trong 2 giây liên tiếp, đảm bảo lượt quét của người mới hoàn toàn độc lập và chính xác.

### Câu 5: Trong giao diện Web Dashboard (`monitor.html`), em sử dụng các thư viện nào? Em tối ưu hóa việc cập nhật DOM như thế nào để trang web không bị đơ hoặc tải chậm khi nhận dữ liệu dồn dập từ Firebase?
* **Thư viện:** Giao diện chỉ sử dụng thư viện lõi Firebase SDK (tải từ CDN gstatic) để liên kết kết nối thời gian thực, hoàn toàn **không sử dụng bất kỳ framework cồng kềnh nào (như React, Angular, Bootstrap)** giúp tải trang cực kỳ nhanh.
* **Tối ưu hóa DOM:** 
  1. Chỉ cập nhật những phần tử thực sự thay đổi giá trị (Ví dụ: chỉ vẽ lại thẻ lịch sử khi nhận sự kiện dòng lịch sử mới được đẩy vào `/history`, thay vì tải lại toàn bộ danh sách).
  2. Sử dụng truy xuất trực tiếp qua ID phần tử (`document.getElementById`) giúp giảm thiểu thời gian phân tích cấu trúc tài liệu HTML của trình duyệt, đảm bảo trang web hoạt động mượt mà ở tốc độ phản hồi 60 FPS.

### Câu 6: Để đánh giá hiệu quả hoạt động của đồ án, em đã thực hiện những bài thử nghiệm thực nghiệm (empirical tests) nào? Kết quả chỉ ra hệ thống có những hạn chế gì cần cải thiện?
* **Thực nghiệm đã làm:**
  1. **Thử nghiệm độ nhạy cảm biến siêu âm:** Xác định góc quét hoạt động tốt nhất là góc trực diện (lệch dưới $15^\circ$), góc lệch lớn hơn dễ gây sai số khoảng cách do sóng âm bị phản xạ phân tán.
  2. **Thử nghiệm độ trễ (Latency Test):** Đo tốc độ phản hồi từ lúc camera chụp đủ 5 khung hình đến lúc Servo xoay (đạt trung bình ~0.45s).
  3. **Thử nghiệm tỷ lệ nhận dạng (Accuracy Test):** Quét thử nghiệm 100 lần trong các điều kiện môi trường. Đạt tỷ lệ đúng 94% ở ánh sáng phòng tiêu chuẩn, nhưng giảm xuống 82% khi gặp ngược sáng mạnh hoặc thiếu sáng.
* **Hạn chế & Hướng cải tiến:** Hạn chế lớn nhất là nhận dạng kém trong bóng tối. Hướng cải tiến là lắp đặt thêm cảm biến quang trở (LDR) kết hợp đèn LED trợ sáng tự động kích hoạt khi có người vào buổi tối.
