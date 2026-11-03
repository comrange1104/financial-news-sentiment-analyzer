# Kịch bản video demo - tối đa 5 phút

## Chuẩn bị

- Mở README, `app/main.py`, `app/services/sentiment.py` và `app/services/article_reader.py` trong editor.
- Cài thư viện và tải model trước buổi quay để không mất thời gian chờ mạng.
- Mở terminal tại thư mục dự án; phóng chữ đủ lớn để đọc trong video.
- Chuẩn bị trình duyệt với `http://127.0.0.1:8000/docs`.
- Quay màn hình bằng công cụ sẵn có trên máy; nói theo các ý bên dưới bằng lời của mình.

## 0:00-0:40 - Giới thiệu

“Em là Trần Hải Thiên, MSSV 25127007. Đề tài là Financial News Sentiment Analyzer. Hệ thống nhận văn bản hoặc URL tin tài chính tiếng Anh và trả sắc thái tích cực, tiêu cực, trung lập cùng điểm của cả ba nhãn. Em sử dụng mô hình ProsusAI/finbert trên Hugging Face, chạy trên CPU qua FastAPI.”

Cho xem link Hugging Face trong README. Nêu rõ dùng mô hình có sẵn, không huấn luyện lại.

## 0:40-1:20 - Cấu trúc code

- `main.py`: ứng dụng, nạp model một lần trong lifespan, ba endpoint bắt buộc.
- `schemas.py`: đúng một nguồn text hoặc URL, trả JSON có cấu trúc.
- `sentiment.py`: chia tối đa 510 token nội dung/đoạn, chạy model, trung bình điểm theo số token.
- `article_reader.py`: kiểm tra URL công khai, tải HTML và trích nội dung chính.
- `tests/` và `test_api_requests.py`: kiểm thử giả lập và kiểm thử server thật bằng requests.

## 1:20-2:00 - Khởi động

Chạy trong terminal:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Chờ khởi động xong. Mở `/health`, chỉ vào `model_ready: true`. Chuyển sang `/docs`, giới thiệu GET `/`, GET `/health`, POST `/predict`.

## 2:00-4:00 - Thử và giải thích

Trong Swagger chọn POST `/predict` > Try it out. Chạy lần lượt:

```json
{"text": "The company reported record profits and raised its annual forecast."}
```

Chỉ vào `label: positive`, `confidence` và `scores`. Giải thích nhãn cuối là nhãn có điểm cao nhất; confidence không phải độ chính xác đã được bảo đảm.

```json
{"text": "The company reported a significant loss and warned of declining sales."}
```

So sánh nhãn `negative` với câu đầu. Nếu còn thời gian, chọn example neutral có sẵn trong Swagger.

Sau đó thử URL:

```json
{"url": "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2025"}
```

Chỉ vào `source_type: url`, URL cuối, `token_count` và `chunk_count`. Giải thích bài dài được xử lý qua nhiều đoạn rồi gộp điểm, không chỉ lấy phần đầu. Nếu website bất ngờ chặn truy cập, minh họa lỗi rồi dùng nội dung dán hoặc URL Federal Reserve trong README.

## 4:00-4:40 - Validation và kết thúc

Gửi:

```json
{"text": "   "}
```

Chỉ ra HTTP `422` và trường `detail`. Mở terminal thứ hai, chạy script (hoặc cho xem kết quả đã chuẩn bị):

```powershell
.venv\Scripts\python.exe test_api_requests.py
```

Giới thiệu README chứa cách cài, cách chạy, request/response và đường dẫn GitHub. Dừng video trước 5:00.

## Sau khi quay

1. Upload video lên YouTube ở chế độ công khai/không công khai, hoặc Google Drive với quyền bất kỳ ai có link đều xem được.
2. Thay mục video ở đầu README bằng link thực tế.
3. Mở link trong cửa sổ ẩn danh để kiểm tra quyền truy cập.
4. Commit và push bản cập nhật README trước khi nộp.

File này là kịch bản quay; không phải video đã được ghi hoặc đã upload.
