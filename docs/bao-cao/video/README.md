# Đoạn quay demo

Quay tự động trên GitHub Actions bằng workflow `demo-recording` (run 42485159867, ngày 08/11/2026), bản thu nhỏ trên kind, không có tiếng. Video 4K (3840x2160, 16:9), 30 hình/giây.

| Tệp | Nội dung | Kết quả trong lần quay | Dùng cho đoạn nào trong kịch bản |
|---|---|---|---|
| `normal.mp4` | Luồng bình thường: pod, `/healthz`, bài viết, bản sao lưu CNPG, Velero, cụm dự phòng | | 2:15-3:30 |
| `D1.mp4` | Xóa nhầm namespace rồi khôi phục tại chỗ | Đạt, RTO 55,7 s, RPO 0 s | 3:30-6:00 |
| `D3.mp4` | Mất cụm chính, chuyển sang cụm dự phòng chạy sẵn (cách ấm) | Đạt, RTO 14,8 s; 36 bài cuối chưa kịp chép sang, vẫn trong RPO cho phép | 6:00-7:45 |
| `D6.mp4` | Thử xóa và ghi đè gói trong két | Đạt | 7:45-8:30 |

Các đoạn ngắn hơn lời thoại vì thời gian chờ đã được rút gọn. Khi ghép, làm chậm hoặc dừng hình ở khung cuối cho khớp tiếng.

Quay lại: `gh workflow run demo-recording.yml --ref demo-recording`, rồi tải artifact `demo-recording`.
