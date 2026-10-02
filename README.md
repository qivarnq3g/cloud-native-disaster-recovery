# Đồ án Điện toán đám mây - Nhóm 23

**Đề tài 23: Thiết kế và kiểm chứng kế hoạch sao lưu phục hồi thảm họa cho ứng dụng cloud native.**

Câu hỏi nghiên cứu: kế hoạch phục hồi có thực sự đạt mục tiêu về lượng dữ liệu được phép mất (RPO) và thời gian được phép ngừng (RTO) hay không, nếu chưa từng thử khôi phục ứng dụng, cấu hình và dữ liệu?

Cách làm: một web nhỏ đăng ảnh kèm mô tả (có cơ sở dữ liệu và kho ảnh) chạy trên hai cụm Kubernetes ở máy cá nhân, một cụm chính và một cụm dự phòng. Nhóm sao lưu, cố tình phá cụm chính, khôi phục sang cụm dự phòng theo hướng dẫn, rồi đo thời gian từng bước và kiểm tra dữ liệu còn đủ hay không.

## Thành viên

| Thành viên | Phần phụ trách |
|---|---|
| Hoàng Việt Quang | Web, hai cụm Kubernetes, sao lưu, script đo và kiểm tra, diễn tập, các chương kỹ thuật |
| Huong-19 | Lý thuyết, đánh giá ảnh hưởng, nháp hướng dẫn khôi phục, tài liệu tham khảo |
| minhthw1605 | Danh sách kiểm tra sau khôi phục, bấm giờ và biên bản diễn tập, ghép báo cáo, slide, video |

Cả ba người đều phải hiểu toàn bộ hệ thống để trả lời vấn đáp.

## Cấu trúc

| Thư mục / tệp | Nội dung | Người làm |
|---|---|---|
| `app/` | Web đăng ảnh | Quang |
| `infra/` | Cấu hình hai cụm Kubernetes | Quang |
| `backup/` | Cấu hình sao lưu | Quang |
| `scripts/` | Script đo thời gian, kiểm tra dữ liệu, vẽ biểu đồ | Quang |
| `data/` | Số liệu đo thô từ các lần diễn tập | Quang |
| `docs/ly-thuyet.md` | Phần lý thuyết | Huong-19 |
| `docs/danh-gia-anh-huong.md` | Đánh giá ảnh hưởng khi web ngừng | Huong-19 |
| `docs/runbook.md` | Hướng dẫn khôi phục | Huong-19 viết nháp, Quang duyệt |
| `docs/checklist-khoi-phuc.md` | Danh sách kiểm tra sau khôi phục | minhthw1605 |
| `docs/dien-tap/` | Biên bản từng lần diễn tập | minhthw1605 |
| `docs/bao-cao/` | Báo cáo, slide, link video | minhthw1605 ghép |

## Quy ước

- Mỗi người tự commit phần của mình. Đề yêu cầu kho có lịch sử đóng góp của cả ba thành viên.
- Không đưa mật khẩu, khóa, tệp cấu hình chứa bí mật hay dữ liệu cá nhân vào kho.
- Bản nghiệm thu được gắn thẻ phiên bản (tag).

## Sản phẩm nộp

- Báo cáo 20-35 trang, nộp trên Moodle, hạn 26/11/2026 02:00.
- Video demo 8-12 phút đăng lên YouTube.
- Trình bày trên lớp và vấn đáp.
