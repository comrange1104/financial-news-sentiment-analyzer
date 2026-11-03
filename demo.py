"""A timed Vietnamese recording walkthrough using real HTTP requests."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

from test_api_requests import validate_prediction

ROOT = Path(__file__).resolve().parent
NVIDIA_URL = "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2025"
FED_URL = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm"
SCENES = (
    ("Giới thiệu đề tài", 30),
    ("Mô hình và cấu trúc mã nguồn", 35),
    ("Khởi động và kiểm tra hệ thống", 25),
    ("Tin tích cực", 25),
    ("Tin tiêu cực", 25),
    ("Tin trung lập", 20),
    ("Đọc bài báo từ URL", 40),
    ("Phân tích văn bản dài", 25),
    ("Kiểm tra dữ liệu không hợp lệ", 25),
    ("Tổng kết", 20),
)


class DemoServer:
    """Reuse the project's server or start one; only stop a process we own."""

    def __init__(self, port):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.process = None
        self.session = requests.Session()
        self.session.trust_env = False
        self.command = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]

    def check(self):
        response = self.session.get(self.base_url + "/", timeout=2)
        response.raise_for_status()
        intro = response.json()
        if (
            not isinstance(intro, dict)
            or intro.get("name") != "Financial News Sentiment Analyzer"
            or intro.get("model") != "ProsusAI/finbert"
        ):
            raise RuntimeError(f"Cổng {self.port} đang chạy ứng dụng khác. Dùng --port 8001.")
        health = self.session.get(self.base_url + "/health", timeout=2)
        data = health.json()
        if (
            health.status_code != 200
            or not isinstance(data, dict)
            or data.get("model_ready") is not True
        ):
            raise RuntimeError("Model chưa sẵn sàng. Kiểm tra log server rồi khởi động lại.")

    def start(self):
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                occupied = True
        except OSError:
            occupied = False
        if occupied:
            self.check()
            print(f"Dùng lại API đang chạy: {self.base_url}")
            return
        log_dir = ROOT / "output" / "demo"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "server.log").open("w", encoding="utf-8") as log:
            self.process = subprocess.Popen(
                self.command,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUTF8": "1"},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        print("Đang nạp FinBERT. Bước chuẩn bị này chưa tính vào 4 phút 30 giây.")
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("Server không khởi động được. Xem output/demo/server.log.")
            try:
                self.check()
                return
            except (requests.ConnectionError, requests.Timeout):
                time.sleep(0.5)
        raise RuntimeError("Chờ server quá 300 giây. Xem output/demo/server.log, rồi chạy lại.")

    def close(self, keep_server=False):
        if self.process is not None and not keep_server and self.process.poll() is None:
            if os.name == "nt":
                # The Windows venv launcher may spawn a second Python process.
                # Stop only this owned process tree, so no orphan keeps the port busy.
                subprocess.run(
                    ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.session.close()


def display_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def show_source():
    print("Model: https://huggingface.co/ProsusAI/finbert\n")
    print("app/main.py                   FastAPI, lifespan, 3 endpoint")
    print("app/schemas.py                Kiểm tra request và response")
    print("app/services/sentiment.py     FinBERT, chia đoạn, gộp điểm")
    print("app/services/article_reader.py  Đọc URL và trích bài")
    print("tests/ + test_api_requests.py Kiểm thử tự động và HTTP thật\n")
    lines = (ROOT / "app" / "main.py").read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if "async def lifespan(" in line)
    print("Trích mã nguồn thật - nạp model một lần:")
    for index in range(start, min(start + 10, len(lines))):
        print(f"{index + 1:>3} | {lines[index]}")


class Walkthrough:
    def __init__(self, server):
        self.server = server
        self.records = []
        self.problems = []

    def call(self, path, payload=None, expected_status=200):
        method = "GET" if payload is None else "POST"
        print(f"{method} {path}")
        if payload is not None:
            if len(payload.get("text", "")) > 300:
                print('Input: "Revenue increased and operating profit improved. " × 150')
            else:
                display_json(payload)
        started = time.monotonic()
        response = self.server.session.request(
            method, self.server.base_url + path, json=payload, timeout=(3, 25)
        )
        data = response.json()
        elapsed = time.monotonic() - started
        print(f"\nHTTP {response.status_code} | {elapsed:.2f} giây")
        display_json(data)
        self.records.append(
            {
                "method": method,
                "path": path,
                "request": payload,
                "status_code": response.status_code,
                "response": data,
                "elapsed_seconds": round(elapsed, 3),
            }
        )
        if response.status_code != expected_status:
            raise RuntimeError(f"Mong đợi HTTP {expected_status}, nhận {response.status_code}.")
        if path == "/predict" and expected_status == 200:
            validate_prediction(data, "url" if "url" in payload else "text")
        return data

    def scene(self, index):
        if index == 0:
            print("FINANCIAL NEWS SENTIMENT ANALYZER\n")
            print("Trần Hải Thiên | MSSV: 25127007")
            print("FastAPI + ProsusAI/finbert | Python 3.12 | CPU\n")
            print("Nhận văn bản hoặc URL tin tài chính tiếng Anh.")
            print("Trả positive / negative / neutral và điểm của cả ba nhãn.")
        elif index == 1:
            show_source()
        elif index == 2:
            print("Lệnh server được dùng trong bước chuẩn bị:")
            print(f"python -m uvicorn app.main:app --host 127.0.0.1 --port {self.server.port}\n")
            print("Server được khởi động trước giờ quay, hoặc dùng lại nếu đã sẵn sàng.\n")
            self.call("/")
            self.call("/health")
            print(f"\nSwagger UI: {self.server.base_url}/docs")
        elif index in {3, 4, 5}:
            texts = [
                "The company reported record profits and raised its annual forecast.",
                "The company reported a significant loss and warned of declining sales.",
                "The company will publish its quarterly report on Tuesday.",
            ]
            result = self.call("/predict", {"text": texts[index - 3]})
            print(f"\nKết quả thực tế: {result['label']}; confidence = {result['confidence']:.4f}.")
            print("Confidence là điểm mô hình, không phải tỷ lệ bảo đảm dự đoán đúng.")
        elif index == 6:
            try:
                self.call("/predict", {"url": NVIDIA_URL})
            except (requests.RequestException, RuntimeError) as exc:
                print(f"\nNguồn NVIDIA chưa đọc được: {exc}")
                print("Thử URL dự phòng Federal Reserve; không dùng kết quả giả.\n")
                self.call("/predict", {"url": FED_URL})
            print("\nsource_url là URL cuối; chunk_count là số đoạn thực sự được phân tích.")
        elif index == 7:
            result = self.call(
                "/predict", {"text": "Revenue increased and operating profit improved. " * 150}
            )
            if result["chunk_count"] <= 1:
                raise RuntimeError("Văn bản dài chưa được chia đoạn.")
            print("\nTối đa 510 token nội dung/đoạn; tổng hợp theo số token, không bỏ phần cuối.")
        elif index == 8:
            self.call("/predict", {"text": "   "}, expected_status=422)
            print("\nDữ liệu trắng bị từ chối bằng HTTP 422 và trường detail.")
        else:
            print("Đã trình diễn GET /, GET /health và POST /predict.")
            print("Ba sắc thái, URL, bài dài và validation đều dùng HTTP thật.")
            if self.problems:
                print("\nCác phần cần kiểm tra lại:")
                for problem in self.problems:
                    print(f"- {problem}")
            else:
                print("\nTất cả phần gọi API trong lượt demo này đã thành công.")
            print("\nREADME: cách cài, chạy, ví dụ request/response và nguồn mô hình.")
            print("GitHub: https://github.com/comrange1104/financial-news-sentiment-analyzer")


def run(args):
    server = DemoServer(args.port)
    walkthrough = Walkthrough(server)
    try:
        server.start()
        print(f"\nAPI sẵn sàng. Swagger: {server.base_url}/docs")
        print("Mở docs/DEMO.md trên điện thoại hoặc màn hình phụ để đọc lời thoại.")
        if not args.fast:
            if args.auto_start:
                print("Bắt đầu sau 5 giây...")
                time.sleep(5)
            else:
                input("Bật quay màn hình, rồi nhấn Enter để bắt đầu demo tự động: ")
        started = time.monotonic()
        planned_elapsed = 0
        for index, (title, seconds) in enumerate(SCENES):
            if sys.stdout.isatty() and not (args.no_clear or args.fast):
                os.system("cls" if os.name == "nt" else "clear")
            print(
                f"\n{'=' * 72}\n{index + 1:02}. {title.upper()} | Mốc {planned_elapsed // 60}:{planned_elapsed % 60:02}\n{'=' * 72}\n"
            )
            try:
                walkthrough.scene(index)
            except (requests.RequestException, RuntimeError, AssertionError, ValueError) as exc:
                message = f"{title}: {exc}"
                walkthrough.problems.append(message)
                print(
                    f"\nCHƯA THÀNH CÔNG: {message}\nTiếp tục phần tiếp theo; không thay bằng dữ liệu giả."
                )
            planned_elapsed += seconds
            if not args.fast:
                print(
                    f"\n[Tự chuyển phần ở mốc {planned_elapsed // 60}:{planned_elapsed % 60:02}; Ctrl+C để dừng]"
                )
                remaining = started + planned_elapsed - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)
        report_path = ROOT / "output" / "demo" / "last_run.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "fast": args.fast,
                    "duration_seconds": round(time.monotonic() - started, 2),
                    "problems": walkthrough.problems,
                    "requests": walkthrough.records,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nĐã kết thúc. Báo cáo HTTP thật: {report_path}")
        return 1 if walkthrough.problems else 0
    finally:
        server.close(keep_server=args.keep_server)
        if server.process is not None and args.keep_server and server.process.poll() is None:
            print(f"Giữ server tại {server.base_url}; PID {server.process.pid}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000, choices=range(1, 65536), metavar="PORT")
    parser.add_argument(
        "--fast", action="store_true", help="Chạy thử ngay, bỏ chờ và bỏ nhịp thời gian"
    )
    parser.add_argument(
        "--auto-start", action="store_true", help="Tự bắt đầu sau 5 giây, không chờ Enter"
    )
    parser.add_argument("--no-clear", action="store_true", help="Giữ toàn bộ đầu ra trên terminal")
    parser.add_argument(
        "--keep-server", action="store_true", help="Giữ server do script tạo sau khi kết thúc"
    )
    args = parser.parse_args()
    try:
        return run(args)
    except KeyboardInterrupt:
        print("\nĐã dừng demo.")
        return 130
    except EOFError:
        print("Không có đầu vào tương tác. Chạy với --auto-start hoặc --fast.", file=sys.stderr)
        return 1
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"\nKhông thể chuẩn bị demo: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
