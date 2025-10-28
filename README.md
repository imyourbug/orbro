Thiết lập môi trường
- Hệ điều hành: Ubuntu 20.04+
- Python: 3.9+
- Thư viện: fastapi, uvicorn

Setup
1) Create venv and install deps
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

Phương pháp thực thi
- Khởi động UDP listener (nhận dòng TAG và cập nhật trạng thái)
   python main.py

- Khởi động API server (ở cửa sổ khác)
   uvicorn api:app --reload --host 0.0.0.0 --port 8000

- Khởi động simulator gửi 3+ Tag ID vào UDP 9999
   python tag_simulator.py --host 127.0.0.1 --port 9999 --interval 1.0

Giải thích phương thức giả lập (Simulation)
- Simulator (`tag_simulator.py`) gửi gói UDP đến 127.0.0.1:9999 theo chu kỳ `--interval`, với tối thiểu 3 Tag ID; mỗi lần gửi, CNT tăng dần.
- Listener (`main.py`) nhận dòng có định dạng:
  - Định dạng: TAG,<tag_id>,<cnt>,<timestamp>
  - Ví dụ: TAG,fa451f0755d8,197,20240503140059.456
- Chỉ Tag đã đăng ký mới được cập nhật trạng thái. Có thể bật auto-increment phía server:
  - AUTO_INCREMENT_CNT=1 python main.py
  - Khi bật, server bỏ qua CNT đầu vào và tự tăng theo DB (1, 2, 3, ...).

Ví dụ kiểm thử API bằng curl
- POST /tags
   curl -X POST http://localhost:8000/tags -H "Content-Type: application/json" \
        -d '{"id":"fa451f0755d8","description":"Helmet Tag for worker A"}'

- GET /tags
   curl http://localhost:8000/tags

- GET /tag/{id}
   curl http://localhost:8000/tag/fa451f0755d8

- GET /health
   curl http://localhost:8000/health

Ghi chú
- Chỉ các Tag đã đăng ký mới được quản lý/tracking. Đăng ký qua POST /tags.
- Mỗi khi CNT thay đổi, hệ thống ghi log ra stdout kèm thời gian.
- Timestamp là UTC; phần thập phân là mili-giây.
- Tùy chọn: đặt AUTO_INCREMENT_CNT=1 để server tự tăng CNT, bỏ qua CNT từ input.

SQLite
- Tệp DB: tags.db (tự tạo). API và UDP listener dùng DB để lưu trạng thái.
- Không cần cấu hình thêm; chỉ cần chạy `python main.py` để khởi tạo DB.
- Reset DB: `python db.py --reset`


### Bài 3: Review cấu trúc bộ nhớ và đề xuất cải thiện
Đoạn code:
```
tag_log = []
def log(tag_id, cnt, timestamp):
    tag_log.append((tag_id, cnt, timestamp))
```
- Vấn đề 1 (tăng trưởng bộ nhớ): `tag_log` là list không giới hạn → có thể phình to và gây out-of-memory.
  - Cải thiện: dùng `collections.deque(maxlen=N)` để giới hạn số log gần nhất; hoặc ghi ra file/SQLite để lưu trữ bền vững (đã minh họa qua `db.py`).
- Vấn đề 2 (không an toàn khi đồng thời): nhiều thread/task async cùng ghi vào list có thể gây race-condition.
  - Cải thiện: dùng `threading.Lock`/`asyncio.Lock` hoặc `queue.Queue`/`asyncio.Queue` để ghi tuần tự; hoặc mô hình actor.
- Vấn đề 3 (truy vấn trạng thái kém hiệu quả): lưu tuple tuyến tính khó lấy “trạng thái cuối” cho mỗi tag (phải duyệt toàn bộ list).
  - Cải thiện: duy trì cấu trúc tra cứu `dict[tag_id] -> {last_cnt, last_seen}` để truy xuất O(1) (đã triển khai trong `main.py`/DB).
- Vấn đề 4 (thiếu xác thực/chuẩn hóa): không kiểm tra hợp lệ của `tag_id/cnt/timestamp`.
  - Cải thiện: parse/validate trước khi lưu (đã thực hiện trong `parser.py`).

