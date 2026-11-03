# Kịch bản quay video - 4 phút 30 giây

Sinh viên: **Trần Hải Thiên - MSSV 25127007**.

## Một lệnh để chạy toàn bộ demo

Mở PowerShell tại thư mục `LAB-2`, chạy:

```powershell
.venv\Scripts\python.exe -X utf8 demo.py
```

Script tự khởi động API nếu cần, chờ FinBERT sẵn sàng rồi mới cho bắt đầu quay. Nếu đúng API của dự án đã chạy ở cổng 8000, script dùng lại. Nếu cổng bị ứng dụng khác chiếm, script báo lỗi và không dừng ứng dụng đó.

Khi thấy **“Bật quay màn hình, rồi nhấn Enter…”**, bật quay và nhấn Enter. Từ đó script tự chuyển qua 10 phần, gọi API thật và hiển thị JSON theo lịch bên dưới. Bạn chỉ cần đọc lời thoại. Thời gian chuẩn bị/tải model không tính vào 4:30; khi mạng chậm, một phần có thể kéo dài và phần sau tự rút thời gian chờ.

Nếu chưa cài môi trường, làm bước cài đặt trong README trước. Script không tự cài thư viện trong lúc quay.

## Bố trí màn hình

1. Quay toàn bộ màn hình hoặc chỉ cửa sổ terminal; phóng chữ khoảng 18-22, giữ chiều rộng đủ đọc JSON.
2. Mở tài liệu này trên điện thoại hoặc màn hình phụ để đọc, tránh chuyển qua lại trong lúc quay.
3. Có thể mở sẵn `http://127.0.0.1:8000/docs` để giới thiệu Swagger; phần gọi API trong video diễn ra trên terminal, không cần bấm từng request.
4. Tắt thông báo cá nhân và thử một lượt nhanh trước khi quay.

## Lời thoại khớp từng phần tự chạy

### 0:00-0:30 - Giới thiệu đề tài

Màn hình: tên đề tài, tên sinh viên, công nghệ và chức năng.

> Em là Trần Hải Thiên, MSSV 25127007. Đề tài của em là Financial News Sentiment Analyzer. Hệ thống nhận văn bản hoặc đường dẫn bài báo tài chính tiếng Anh, sau đó phân loại thành tích cực, tiêu cực hoặc trung lập. Kết quả gồm nhãn được chọn, điểm của cả ba nhãn và thông tin số đoạn đã được phân tích. Em xây dựng API bằng FastAPI và sử dụng mô hình FinBERT chạy trên CPU.

### 0:30-1:05 - Mô hình và cấu trúc mã nguồn

Màn hình: link Hugging Face, cấu trúc file và trích đoạn `lifespan` từ mã nguồn thật.

> Em chọn mô hình ProsusAI/finbert trên Hugging Face vì mô hình được thiết kế cho phân tích sắc thái văn bản tài chính tiếng Anh. Em sử dụng mô hình đã được huấn luyện sẵn. Trong mã nguồn, main.py khởi tạo FastAPI và khai báo các endpoint. schemas.py kiểm tra dữ liệu đầu vào, đầu ra. sentiment.py xử lý mô hình và bài dài; article_reader.py tải và trích nội dung bài báo. Mô hình được nạp một lần trong lifespan để dùng chung giữa các request.

### 1:05-1:30 - Khởi động và kiểm tra hệ thống

Màn hình: lệnh chạy Uvicorn, JSON thật từ `GET /` và `GET /health`, đường dẫn Swagger.

> Lệnh trên màn hình dùng Uvicorn để chạy API tại localhost, cổng 8000. Script đã chuẩn bị server trước khi bắt đầu phần quay; nếu API đang chạy thì dùng lại. Endpoint GET gốc giới thiệu hệ thống. GET health trả trạng thái hoạt động và model_ready bằng true khi mô hình sẵn sàng. Ngoài ra, đường dẫn docs cung cấp Swagger UI để xem tài liệu và thử các endpoint.

### 1:30-1:55 - Tin tích cực

Màn hình: POST `/predict`, câu lợi nhuận kỷ lục và response.

> Với đầu vào thứ nhất, công ty công bố lợi nhuận kỷ lục và nâng dự báo cả năm. Đây là thông tin mang sắc thái tích cực. Kết quả thực tế được hiển thị ở trường label. API đồng thời trả điểm positive, negative và neutral. Nhãn được chọn là nhãn có điểm cao nhất, còn confidence chính là điểm của nhãn đó. Điểm này không phải tỷ lệ bảo đảm mô hình dự đoán đúng.

### 1:55-2:20 - Tin tiêu cực

Màn hình: câu thua lỗ và doanh số giảm cùng response.

> Ở đầu vào thứ hai, công ty công bố thua lỗ đáng kể và cảnh báo doanh số suy giảm. Ta có thể so sánh nhãn và ba điểm số với ví dụ trước. Cùng một endpoint predict nhưng nội dung khác nhau sẽ tạo kết quả khác nhau. Các kết quả trên màn hình được gọi trực tiếp từ API đang chạy và mô hình FinBERT thật, không phải JSON được viết sẵn để minh họa.

### 2:20-2:40 - Tin trung lập

Màn hình: thông báo ngày công bố báo cáo quý cùng response.

> Ví dụ thứ ba chỉ thông báo công ty sẽ công bố báo cáo quý vào thứ Ba. Câu không nêu kết quả kinh doanh tốt hay xấu nên dùng để minh họa sắc thái trung lập. Ta quan sát điểm neutral và nhãn cuối cùng. Như vậy API đã được thử bằng ba đầu vào thể hiện ba sắc thái khác nhau.

### 2:40-3:20 - Đọc bài báo từ URL

Màn hình: URL NVIDIA và kết quả thật; nếu lỗi, tự thử nguồn Federal Reserve.

> Ngoài văn bản dán trực tiếp, API còn nhận URL. Trong ví dụ này, hệ thống tải một bài công bố kết quả tài chính từ website NVIDIA. HTTPX thực hiện tải HTML, sau đó Trafilatura trích nội dung chính trước khi chuyển cho FinBERT. Trường source_type cho biết nguồn là URL; source_url là đường dẫn cuối cùng sau chuyển hướng. API chỉ cho phép đích công khai và kiểm tra lại mỗi lần chuyển hướng. Trang có paywall, chặn bot hoặc cần JavaScript có thể không đọc được.

**Nếu script chuyển nguồn:** nói “Nguồn NVIDIA hiện chưa đọc được, nên script thử nguồn công khai dự phòng từ Federal Reserve.” Đọc kết quả thực tế; không khẳng định nhãn trước khi nhìn response. Nếu cả hai URL lỗi, nói rõ hạn chế truy cập và tiếp tục phần kế tiếp; script sẽ ghi nhận lỗi, không giả kết quả thành công.

### 3:20-3:45 - Văn bản dài

Màn hình: đoạn tin lặp 150 lần, số token và số đoạn thực tế.

> Mô hình chỉ nhận tối đa 512 token mỗi lần, gồm các token đặc biệt. Vì vậy ứng dụng chia bài dài thành các đoạn tối đa 510 token nội dung, không chồng lặp. Ví dụ này được tạo bằng cách lặp một đoạn tin để kiểm tra cơ chế chia đoạn. Ta quan sát token_count và chunk_count. Điểm cuối cùng được tính trung bình có trọng số theo số token của từng đoạn, thay vì chỉ phân tích phần đầu bài.

### 3:45-4:10 - Validation và xử lý lỗi

Màn hình: gửi chuỗi trắng, nhận HTTP `422` và `detail`.

> Tiếp theo, em gửi một chuỗi chỉ chứa khoảng trắng. API từ chối yêu cầu với mã HTTP 422 và trường detail giải thích lỗi. Hệ thống cũng kiểm tra phải có đúng một nguồn text hoặc URL, không chấp nhận sai kiểu dữ liệu hoặc vượt giới hạn token. Các lỗi tải bài, timeout và mô hình không khả dụng được trả bằng những mã lỗi phù hợp, còn chi tiết lỗi kỹ thuật được ghi vào log.

### 4:10-4:30 - Tổng kết

Màn hình: tóm tắt các chức năng đã trình diễn và link GitHub.

> Qua phần demo, hệ thống đã trình diễn ba endpoint bắt buộc, phân tích ba sắc thái, đọc URL, xử lý văn bản dài và kiểm tra đầu vào. Repository GitHub công khai có đầy đủ mã nguồn, requirements.txt, README và script kiểm thử bằng requests. README hướng dẫn cách cài, chạy và gọi API. Đây là hệ thống phân loại sắc thái văn bản, chưa có chức năng dự báo giá. Em xin kết thúc phần trình bày.

Nếu có phần lỗi trong lượt quay, nói đúng theo báo cáo trên màn hình và quay lại sau khi khắc phục. Dừng video trước 5 phút.

## Chạy thử và tùy chọn

Chạy thử nhanh, không chờ Enter và không đợi hết từng mốc:

```powershell
.venv\Scripts\python.exe -X utf8 demo.py --fast
```

- `--auto-start`: không chờ Enter, đếm 5 giây rồi tự bắt đầu.
- `--port 8001`: dùng cổng khác nếu 8000 bị ứng dụng khác chiếm.
- `--no-clear`: giữ toàn bộ đầu ra thay vì xóa màn hình giữa các phần.
- `--keep-server`: giữ server mà script tự tạo sau khi demo kết thúc.

Mặc định script dừng server do chính nó tạo khi kết thúc hoặc khi nhấn Ctrl+C. Server có sẵn được dùng lại và **không bị dừng**. Báo cáo HTTP thật được lưu trong `output/demo/last_run.json`; log khởi động trong `output/demo/server.log` nếu script tự tạo server. Hai file này được Git bỏ qua. Mã thoát khác 0 cho biết lượt demo có lỗi; phần chuẩn bị hoặc URL có thể lỗi nếu mạng/website không khả dụng.

## Sau khi quay

Upload video lên YouTube hoặc Google Drive, bật quyền người có link được xem và thử bằng cửa sổ ẩn danh. Thay mục video ở đầu README bằng link thật rồi commit/push. Bổ sung thông tin lớp nếu cần.

Tài liệu này là lời thoại và hướng dẫn chạy; script không tự quay màn hình, thu âm hoặc upload video.
