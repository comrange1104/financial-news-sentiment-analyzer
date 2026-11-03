# Financial News Sentiment Analyzer

API phân tích sắc thái **tin tức tài chính tiếng Anh** bằng FastAPI và FinBERT. Người dùng gửi văn bản hoặc URL bài báo HTML công khai; hệ thống trả nhãn `positive`, `negative`, `neutral`, điểm của cả ba nhãn và thông tin số token/đoạn đã phân tích.

Repository công khai: [comrange1104/financial-news-sentiment-analyzer](https://github.com/comrange1104/financial-news-sentiment-analyzer).

## Thông tin sinh viên

| Mục | Thông tin |
| --- | --- |
| Họ tên | Trần Hải Thiên |
| MSSV | 25127007 |
| Lớp | Chưa cung cấp |
| Học phần | Computational Thinking - API Lab |
| Video demo, tối đa 5 phút | **Chưa có - cần bổ sung link công khai trước khi nộp** |

Kịch bản quay video: [docs/DEMO.md](docs/DEMO.md). Kết quả kiểm chứng: [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Mô hình và cách phân tích

- Model: [ProsusAI/finbert trên Hugging Face](https://huggingface.co/ProsusAI/finbert).
- Revision cố định: `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` để tái lập kết quả.
- Mô hình BERT chuyên cho văn bản tài chính tiếng Anh, đã được tinh chỉnh cho phân loại sentiment; không huấn luyện lại trong bài này.
- Nhãn của model: `0 = positive`, `1 = negative`, `2 = neutral`. Mã nguồn đọc mapping từ cấu hình model, không giả định thứ tự logits.
- Dùng Transformers và PyTorch CPU; không cần API key hoặc GPU.

Luồng xử lý:

```text
text -----------------------------+
                                  v
url -> HTTPX -> Trafilatura -> làm sạch -> token hóa -> chia đoạn
                                                          |
                                                          v
                                                       FinBERT
                                                          |
                                                          v
                                               tổng hợp điểm -> JSON
```

Mô hình và tokenizer được nạp một lần trong `lifespan` của ứng dụng. Các request dùng chung mô hình. Nếu nạp thất bại, server vẫn cho truy cập `/health` và `/docs`; `/predict` trả `503`. Xem log, khắc phục rồi khởi động lại.

### Văn bản dài và điểm tin cậy

Giới hạn mỗi request là **20.000 token nội dung**. Token là các đơn vị do tokenizer BERT tạo ra, không đồng nghĩa số từ. Văn bản được chuẩn hóa khoảng trắng và chia thành các đoạn liên tiếp, không chồng lặp, tối đa **510 token nội dung** mỗi đoạn; `[CLS]` và `[SEP]` đưa tổng đầu vào của mô hình lên tối đa 512.

Với đoạn thứ `i` có `n_i` token nội dung và điểm của nhãn `c` là `p_i(c)`:

```text
score(c) = sum(n_i * p_i(c)) / sum(n_i)
label = nhãn có score cao nhất
confidence = score(label)
```

Chuẩn hóa tổng ba điểm về 1 để bù sai số số thực. Không bỏ phần cuối bài. Vượt 20.000 token thì trả `422`, không âm thầm cắt ngắn. Trước token hóa, giới hạn chuỗi đầu vào là 1.000.000 ký tự.

**Ý nghĩa:** điểm softmax biểu thị mức mô hình nghiêng về từng nhãn; `0.95` không phải bảo đảm 95% dự đoán đúng. Tổng hợp toàn bài là quy tắc của ứng dụng, chưa được hiệu chuẩn như một mô hình phân loại tài liệu riêng. Bài có nội dung trái chiều có thể mất sắc thái khi gộp; ranh giới đoạn có thể cắt qua câu.

## Cài đặt và chạy trên Windows

Yêu cầu **Python 3.12 64-bit**. Dùng các lệnh sau tại thư mục chứa README:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Không cần activate môi trường ảo hoặc thay đổi PowerShell ExecutionPolicy. `requirements.txt` chọn PyTorch CPU qua nguồn wheel chính thức của PyTorch.

Lần chạy đầu cần Internet để tải model (trọng số khoảng 440 MB); lần sau dùng cache Hugging Face trong thư mục người dùng. Chờ dòng `Application startup complete` rồi kiểm tra `/health`. Cache trên Windows có thể báo không hỗ trợ symlink; việc tải và suy luận vẫn hoạt động. Không cần chạy bằng quyền Administrator.

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json).
- Dừng server bằng `Ctrl+C`.

Để chạy trên Linux/macOS, tạo môi trường bằng `python3.12 -m venv .venv`, thay `.venv\Scripts\python.exe` bằng `.venv/bin/python` trong các lệnh tiếp theo. Môi trường đã kiểm chứng của bài là Windows/Python 3.12.

## API

| Method và endpoint | Mô tả |
| --- | --- |
| `GET /` | Giới thiệu chức năng, tên model, ngôn ngữ và đường dẫn tài liệu. |
| `GET /health` | `200` khi mô hình sẵn sàng; `503` khi mô hình không khả dụng. |
| `POST /predict` | Phân tích đúng một nguồn: `text` hoặc `url`. |

### Nhập văn bản

```json
{
  "text": "The company reported record profits and raised its annual forecast."
}
```

Ví dụ gọi bằng Python, sau khi server đã chạy:

```python
import requests

response = requests.post(
    "http://127.0.0.1:8000/predict",
    json={"text": "The company reported record profits and raised its annual forecast."},
    timeout=60,
)
response.raise_for_status()
print(response.json())
```

Kết quả từ FinBERT thật, làm tròn để dễ đọc; các chữ số cuối có thể khác nhẹ theo môi trường:

```json
{
  "model": "ProsusAI/finbert",
  "label": "positive",
  "confidence": 0.950812,
  "scores": {
    "positive": 0.950812,
    "negative": 0.022311,
    "neutral": 0.026877
  },
  "source_type": "text",
  "source_url": null,
  "token_count": 11,
  "chunk_count": 1,
  "aggregation": "token_weighted_mean"
}
```

### Nhập URL

```json
{
  "url": "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2025"
}
```

Kết quả có cùng cấu trúc, `source_type` là `url` và `source_url` là URL cuối cùng sau chuyển hướng. Nội dung chính được trích bằng Trafilatura, loại bình luận và bảng. Không trả lại toàn bộ bài trong response.

Hai URL đã thử thành công ngày 03/11/2026:

- [Federal Reserve - FOMC statement, 18/09/2024](https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm).
- [NVIDIA - Financial Results for Second Quarter Fiscal 2025](https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2025).

Chỉ hỗ trợ HTTP/HTTPS qua cổng 80/443. Không chấp nhận thông tin đăng nhập trong URL, localhost, địa chỉ private/link-local/multicast hoặc DNS có bất kỳ địa chỉ không công khai nào. Kết nối được ghim vào IP đã kiểm tra, giữ Host/SNI và xác thực chứng chỉ HTTPS; tắt proxy môi trường và kiểm tra lại từng đích chuyển hướng. Tối đa ba lần chuyển hướng, timeout tải 15 giây và tối đa 5 MiB HTML; DNS hệ điều hành có thể mất thêm thời gian trước khi trả kết quả.

Không chạy JavaScript hoặc đăng nhập vào website. Trang chặn bot, có paywall hay HTML thay đổi có thể không đọc được; hãy dán văn bản thay thế. Trích nội dung là heuristic, không bảo đảm lấy đúng toàn bộ bài trên mọi website. Đoạn trích ngắn dưới 80 ký tự bị từ chối để tránh phân tích trang rỗng. Swagger có sẵn ví dụ URL NVIDIA để tiện demo.

### Lỗi và validation

| HTTP | Tình huống |
| --- | --- |
| `422` | Thiếu đầu vào; gửi cả hai trường; chuỗi trắng, `null`, sai kiểu, trường lạ; URL không hợp lệ/bị cấm; vượt giới hạn nội dung. |
| `502` | Không phân giải được DNS; website trả lỗi; quá nhiều chuyển hướng; không phải HTML; quá dung lượng; không trích được bài. |
| `504` | Hết thời gian tải bài. |
| `503` | Mô hình chưa sẵn sàng hoặc tải thất bại. |
| `500` | Lỗi xử lý ngoài dự kiến; chi tiết kỹ thuật chỉ ghi trong log. |

Tất cả lỗi có trường `detail`. Validation của FastAPI/Pydantic trả danh sách lỗi; lỗi nghiệp vụ trả chuỗi:

```json
{"detail": "URL must resolve exclusively to public IP addresses."}
```

Chỉ hỗ trợ dữ liệu tiếng Anh theo phạm vi bài; chưa tự nhận diện ngôn ngữ hoặc dịch. API chưa xác minh một văn bản có thực sự là tin tài chính hay không.

## Cấu trúc mã nguồn

```text
app/
  main.py                    FastAPI, lifespan, route và HTTP errors
  schemas.py                 Request/response và validation
  config.py                  Model revision và giới hạn xử lý
  errors.py                  Lỗi nghiệp vụ dùng chung
  services/
    sentiment.py             FinBERT, chia đoạn, tổng hợp điểm
    article_reader.py        URL công khai, tải HTML, trích bài
tests/
  test_api.py                Contract API, lifecycle và lỗi
  test_sentiment.py          Bao phủ token, giới hạn, nhãn và điểm
  test_article_reader.py     URL, DNS, redirect, timeout và extraction
test_api_requests.py         Kiểm thử server thật bằng requests
docs/
  DEMO.md                    Kịch bản quay video
  VERIFICATION.md            Kết quả kiểm thử thực tế
requirements.txt             Dependency đã chốt phiên bản
```

Không có database, giao diện riêng hoặc notebook; model chạy trực tiếp trên CPU của máy.

## Kiểm thử

Test tự động độc lập mạng và không tải model:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Test endpoint và FinBERT thật, mở terminal thứ hai trong khi server đang chạy:

```powershell
.venv\Scripts\python.exe test_api_requests.py
```

Test thêm cả hai URL công khai:

```powershell
.venv\Scripts\python.exe test_api_requests.py --url https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm --url https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2025
```

Script kiểm tra mã HTTP, ba nhãn mẫu, tính hợp lệ/tổng điểm, metadata, văn bản dài và bảy đầu vào không hợp lệ. Không có URL nào được tải trong bộ unit test; test mạng thực tế chỉ chạy khi thêm `--url`. Kết quả test URL phụ thuộc tình trạng website tại thời điểm chạy. Các test minh họa không phải đánh giá accuracy trên tập dữ liệu độc lập.

## Giấy phép và nguồn tham khảo

- [FinBERT model card](https://huggingface.co/ProsusAI/finbert): trọng số được ghi nhận theo **CC BY-NC-SA 4.0**. Dẫn nguồn model khi sử dụng; không đưa trọng số vào repository.
- [FinBERT: Financial Sentiment Analysis with Pre-trained Language Models](https://arxiv.org/abs/1908.10063), Dogu Araci, 2019.
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/).
- [HTTPX SNI extension](https://www.python-httpx.org/advanced/extensions/).
- [Trafilatura extraction](https://trafilatura.readthedocs.io/en/latest/corefunctions.html).

API này thực hiện phân loại sắc thái văn bản; không có chức năng dự báo giá hoặc đề xuất giao dịch.
