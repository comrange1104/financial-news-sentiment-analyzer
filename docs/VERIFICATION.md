# Kết quả kiểm chứng

Ngày kiểm chứng: **03/11/2026**, múi giờ Asia/Saigon. Đây là kết quả chạy thực tế, không phải chỉ tiêu độ chính xác trên tập dữ liệu độc lập.

## Môi trường

- Windows, Python 3.12.10 64-bit, CPU.
- FastAPI 0.162.0, Pydantic 2.14.2, Uvicorn 0.54.0.
- Transformers 4.57.6, PyTorch 2.15.0+cpu.
- HTTPX 0.28.1, Trafilatura 2.3.1, requests 2.34.2.
- Model `ProsusAI/finbert`, revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`.

## Kiểm tra tự động

| Kiểm tra | Kết quả |
| --- | --- |
| `python -m pytest -q` | **72 passed**; không tải model hoặc truy cập mạng trong test. |
| `ruff check app tests test_api_requests.py` | Passed. |
| `ruff format --check app tests test_api_requests.py` | Passed; 12 file Python. |
| `python -m pip check` | Không có dependency xung đột. |
| `pip install --dry-run --ignore-installed -r requirements.txt` | Phân giải được toàn bộ dependency và wheel Python 3.12/Windows. |
| Cài mới bằng `pip install -r requirements.txt` trong môi trường trống | Thành công; **72 test passed**, `pip check` không có xung đột. |
| Nạp FinBERT và suy luận từ môi trường vừa cài mới | Thành công; câu lợi nhuận kỷ lục trả `positive`, confidence `0.950812`. |

Pytest có một cảnh báo deprecation từ Starlette TestClient về việc sử dụng HTTPX thay cho HTTPX2; cả 72 test vẫn thành công. HTTPX cũng là thư viện được dùng có chủ đích cho dịch vụ tải bài.

Các test bao phủ: lifecycle nạp model một lần; model unavailable; request thiếu/sai; schema response; lỗi inference; bao phủ token không trùng/mất; trung bình điểm theo độ dài; mapping nhãn khác thứ tự; giới hạn 20.000 token; IP nội bộ/multicast; DNS hỗn hợp public/private; kết nối IP đã ghim và Host/SNI; redirect vào localhost và redirect loop; timeout; lỗi HTTP; nội dung không phải HTML; giới hạn dung lượng có hoặc không có Content-Length; trích nội dung và loại navigation.

## Kiểm thử server với FinBERT thật

Lệnh:

```powershell
.venv\Scripts\python.exe test_api_requests.py --url https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm --url https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2025
```

Kết quả: **PASS** cho ba endpoint hệ thống/tài liệu, bốn dự đoán văn bản, bảy đầu vào không hợp lệ và hai URL. Điểm trong bảng được làm tròn.

| Đầu vào | Nhãn | Confidence | Token | Đoạn |
| --- | --- | --- | --- | --- |
| Record profits, raised forecast | positive | 0.950812 | 11 | 1 |
| Significant loss, declining sales | negative | 0.972751 | 12 | 1 |
| Quarterly report scheduled for Tuesday | neutral | 0.925079 | 10 | 1 |
| Revenue increased… lặp 150 lần | positive | 0.746172 | 1.050 | 3 |
| Federal Reserve, statement ngày 18/09/2024 | neutral | 0.707715 | 477 | 1 |
| NVIDIA, second quarter fiscal 2025 results | positive | 0.676499 | 1.998 | 4 |

Kiểm tra bổ sung với model thật: chuỗi `"profit " * 20000` trả `200`, `token_count = 20000`, `chunk_count = 40`. Chuỗi `"profit " * 20001` trả `422` trong script tích hợp. Không cắt bỏ phần cuối bài để vừa cửa sổ 512 token.

Kết quả URL phụ thuộc HTML và tình trạng truy cập của nguồn tại thời điểm chạy. Không đưa nội dung đầy đủ của bài báo hoặc trọng số model vào repository.

## Phần cần sinh viên hoàn thiện trước khi nộp

- Bổ sung lớp vào README.
- Quay video theo [DEMO.md](DEMO.md), tối đa 5 phút.
- Upload video, kiểm tra quyền chia sẻ, thay chỗ trống ở README bằng link thật rồi commit/push.

Chưa có video demo được ghi hoặc upload trong lần triển khai này.
