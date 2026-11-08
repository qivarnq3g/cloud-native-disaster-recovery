# Kịch bản video demo

Video 8-12 phút, đăng YouTube, sau đó ghi link vào [README](README.md) và vào mục "Phần bổ sung sản phẩm" của báo cáo. Video phải cho thấy hệ thống chạy bình thường và ít nhất một tình huống lỗi, kèm số liệu và lệnh chạy lại được (đề tài, trang 1).

Tổng thời lượng dự kiến: khoảng 10 phút 30 giây.

## Chuẩn bị trước khi quay

- Máy có Docker, `kind`, `kubectl`, Helm, Python theo [scripts/kind/README.md](../../scripts/kind/README.md). Trên Windows, chạy trong terminal WSL2.
- Dựng sẵn cả hai cụm (khoảng 4 phút, không cần quay):

```bash
scripts/kind/up.sh
```

- Mở sẵn: [slide.pptx](slide.pptx), một terminal chữ to (cỡ 16 trở lên), trình duyệt ở `http://127.0.0.1:18080/healthz`.
- Phần chạy lâu (khởi động, chờ 90 giây đăng bài) cắt hoặc tua nhanh khi dựng video, nhưng giữ nguyên dòng log có mốc thời gian để người xem kiểm được.

## Phân đoạn

| Thời gian | Người nói | Màn hình | Nội dung |
|---|---|---|---|
| 0:00-0:45 | Thư | Slide 1-2 | Giới thiệu nhóm, câu hỏi nghiên cứu và ba mục tiêu: RTO lạnh 60 phút, RTO ấm 10 phút, RPO 5 phút |
| 0:45-2:15 | Hương | Slide 3-6 | Bảng ảnh hưởng nghiệp vụ, kiến trúc, sao lưu ba tầng, bảy kịch bản D1-D7 |
| 2:15-3:30 | Quang | Terminal, trình duyệt | Luồng bình thường trên bản thu nhỏ: hệ thống đang chạy, có dữ liệu và bản sao lưu |
| 3:30-6:00 | Quang | Terminal | Tình huống lỗi 1: D1 xóa nhầm namespace, khôi phục tại chỗ |
| 6:00-7:45 | Quang | Terminal | Tình huống lỗi 2: D3 mất cụm chính, chuyển sang cụm dự phòng (cách ấm) |
| 7:45-8:30 | Quang | Terminal | D6: thử xóa két chống xóa, két từ chối |
| 8:30-10:00 | Thư | Slide 8-12 | Kết quả trên Azure: vòng thử lộ 7 lỗi, vòng chính thức 15/17 lần đạt, điểm nghẽn, D6/D7, 119 lần trên kind |
| 10:00-10:30 | Hương | Slide 13-14 | Chi phí 5,70 USD, lạnh hay ấm, kết luận và hướng phát triển |

## Lời thoại và lệnh

### 2:15-3:30 Luồng bình thường (Quang)

Lời: "Đây là bản thu nhỏ chạy trên một máy, cùng ứng dụng và cùng cách sao lưu như trên Azure. Cụm chính đang phục vụ, đã có 1.000 bài kèm ảnh."

```bash
kubectl --context kind-primary get pods -n dr-api
curl -s http://127.0.0.1:18080/healthz
kubectl --context kind-primary get backups.postgresql.cnpg.io -n dr-api
kubectl --context kind-primary get backups.velero.io -n velero
```

Lời: "Cơ sở dữ liệu đẩy nhật ký thay đổi sang kho sao lưu ít nhất mỗi phút, nên dữ liệu mất tối đa khoảng một phút. Cấu hình Kubernetes được Velero sao lưu theo lịch."

### 3:30-6:00 Tình huống lỗi 1: xóa nhầm namespace (Quang)

Lời: "Giả sử người vận hành xóa nhầm toàn bộ namespace của ứng dụng. Kịch bản D1 vừa đăng bài liên tục, vừa phá, vừa đo từng bước."

```bash
scripts/kind/run.sh D1
```

Chỉ trên màn hình, theo thứ tự log:

1. 90 giây đăng 1 bài mỗi giây (tua nhanh).
2. Namespace bị xóa, `/healthz` hỏng 5 lần liên tiếp: bước phát hiện.
3. CNPG dựng lại cơ sở dữ liệu từ bản đầy đủ và WAL, Velero khôi phục cấu hình.
4. Kiểm tra: đếm bài, so mã nội dung, tải từng ảnh so SHA-256, đăng thử một bài.

Lời khi có kết quả: đọc RTO và RPO trong dòng cuối, so với mục tiêu. Ở 30 lần chạy trên GitHub Actions, RTO của D1 có trung vị 56,9 s.

### 6:00-7:45 Tình huống lỗi 2: mất cụm chính, cách ấm (Quang)

Lời: "Bây giờ mất hẳn cụm chính. Cụm dự phòng đã chạy sẵn bản sao cơ sở dữ liệu, chỉ cần nâng lên làm cụm chính."

```bash
scripts/kind/run.sh D3
```

Lời khi có kết quả: RTO trung vị 13,7 s trên bản thu nhỏ (30 lần); trên Azure là 265 s, phần lớn nằm ở bước nâng cụm dự phòng (khoảng 215 s) và đổi DNS (khoảng 18 s).

### 7:45-8:30 Két chống xóa (Quang)

```bash
scripts/kind/down.sh
scripts/kind/up.sh --profile primary
scripts/kind/run.sh D6
```

Phần `down.sh` và `up.sh` chỉ quay câu lệnh rồi cắt. Lời: "Két bật khóa ghi một lần. Dùng cả khóa quản trị để xóa và ghi đè, cả hai đều bị từ chối."

### 8:30-10:00 Kết quả trên Azure (Thư)

- Slide 8: vòng thử có 7/12 lần không đạt, mỗi lần lộ một lỗi thật (Velero lấy bản cũ, jsonpath sai, máy ảo kẹt, chính sách chép ảnh cũ chặn ghi). Đây là câu trả lời cho câu hỏi nghiên cứu: kế hoạch trên giấy chưa chạy được ngay.
- Slide 9: sau khi sửa, 15/17 lần đạt; RTO lạnh lớn nhất 645,5 s, ấm 265,7 s, RPO bài viết lớn nhất 50,9 s.
- Slide 10: điểm nghẽn là bước khôi phục dữ liệu.
- Slide 11-12: két từ chối mọi cách xóa; khôi phục ngoài Azure 59 s; 119 lần trên kind đều đạt.

### 10:00-10:30 Kết luận (Hương)

Slide 13-14: chi phí thật 5,70 USD; cách lạnh khoảng 1 USD mỗi tháng và đủ mục tiêu 60 phút, cách ấm khoảng 44 USD mỗi tháng. Kết thúc bằng hướng phát triển.

## Sau khi quay

- Dọn môi trường: `scripts/kind/down.sh`.
- Đăng YouTube ở chế độ "Không công khai" hoặc "Công khai", dán link vào dòng "Link video" của [README](README.md) và vào báo cáo.
