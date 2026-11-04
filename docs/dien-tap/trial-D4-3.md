# Biên bản diễn tập trial-D4-3

- Mã lần: `trial-D4-3`
- Tình huống: D4, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển lạnh sang cụm dự phòng dựng mới, ảnh lấy từ kho bản sao ở Nhật
- Ngày: 04/11/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 01:56:40
- Phiên bản mã (commit): 7c90cf1

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 01:56:41 | 01:57:06 | 24,3 | | ok |
| decide - quyết định | 01:57:06 | 01:57:11 | 4,8 | | ok |
| infra - dựng hạ tầng | 01:57:11 | 02:00:31 | 200,1 | | ok |
| restore - khôi phục dữ liệu | 02:00:31 | 02:06:16 | 344,6 | | ok |
| switch - chuyển lưu lượng | 02:06:16 | 02:06:30 | 13,9 | | ok |
| verify - kiểm tra | 02:06:30 | 02:07:19 | 49,5 | | fail |

- RTO từ lúc phá tới khi phục vụ lại: 588,4 s, mục tiêu 60 phút, đạt. Bước restore gồm chép 2.022 ảnh từ kho bản sao sang kho dự phòng trong 294 s, chạy song song với cài phần mềm và khôi phục cơ sở dữ liệu.
- Kết quả kiểm tra lúc chạy: 1101 bài đã xác nhận, còn 1077, thiếu 24 (RPO 18,147 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1103 ảnh kiểm, 16 ảnh không tải được, đăng bài mới được.
- Kết luận lúc chạy: không đạt, vì luật kiểm tra khi đó coi mọi ảnh không tải được là hỏng.
- Phân tích 16 ảnh: đều là ảnh của 16 bài cuối cùng còn lại, đăng từ 17,4 s tới 32,4 s trước lúc phá. Bản ghi của các bài này đã lên kho sao lưu cơ sở dữ liệu, nhưng ảnh chưa kịp chép từ kho chính sang kho bản sao ở Nhật (chép bất đồng bộ, đo trước đây có trung vị 52,7 s, p95 128,7 s). Kho chính mất cùng nhóm tài nguyên nên các ảnh này mất hẳn. Thiết kế đặt RPO của ảnh là 5 phút, nên đây là dữ liệu mất trong mục tiêu, không phải lỗi khôi phục.
- Chấm lại theo luật mới, trên đúng dữ liệu đã khôi phục ở cụm dự phòng, trước khi dựng lại: 0 ảnh hỏng, 16 ảnh mất trong RPO ảnh, các chỉ số bài viết như trên. Kết luận chấm lại: đạt.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không đổi bước nào. Sửa luật kiểm tra trong `scripts/kind/verify.py` và `azure_drill.py`: ảnh không tải được của bài đăng trong vòng RPO ảnh (300 s) trước sự cố được tính là mất trong RPO; ảnh không tải được của bài cũ hơn, hoặc ảnh sai mã băm, vẫn là hỏng.
