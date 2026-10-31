# Hướng dẫn khôi phục (runbook)

Huong-19 viết nháp theo đúng các bước Quang thực hiện; Quang duyệt. Sau mỗi lần diễn tập, sửa lại những bước sai hoặc thiếu và ghi vào lịch sử thay đổi. Bản này viết lại theo vòng thử ngày 31/10/2026 (biên bản trong `docs/dien-tap/`).

Mọi lệnh chạy trong Git Bash, đứng ở thư mục gốc của kho mã. Lệnh nào có `<run_id>` thì giờ bắt đầu, giờ kết thúc và kết quả của bước được ghi tự động vào `data/azure/drills/<run_id>/steps.csv` qua `scripts/azure/step.sh`. Khi xảy ra sự cố thật, đặt `<run_id>` theo mẫu `incident-<ngày giờ>`.

## Khi nào kích hoạt

- Trang `https://api.dr.qivarn.id.vn/healthz` trả lỗi hoặc không trả lời 5 lần liên tiếp, mỗi lần cách nhau 1 giây, trong khi mạng ở máy người trực vẫn vào được `https://www.gstatic.com/generate_204`. Script `python -m scripts.dr.azure_drill` theo dõi đúng điều kiện này.
- Hoặc người trực thấy namespace `dr-api`, máy `vm-dr-primary` hay nhóm `rg-dr-primary` đã bị xóa.

## Ai quyết định

- Quang quyết định. Quang không liên lạc được trong 15 phút thì Huong-19 quyết định.
- Người quyết định ghi lại giờ quyết định. Khi chạy bằng `azure_drill`, giờ nhấn Enter là mốc kết thúc bước `decide`.

## Chọn cách khôi phục

| Tình huống | Cách | Lệnh chính |
|---|---|---|
| Mất namespace `dr-api`, máy chính còn | Khôi phục tại chỗ về 1 giây trước sự cố | `restore-namespace.sh` |
| Mất máy chính, chưa có cụm dự phòng ấm | Chuyển lạnh sang `standby` | `failover-cold.sh` |
| Mất máy chính, đang có cụm dự phòng ấm (`standby-up.sh` đã chạy) | Chuyển ấm | `failover-warm.sh` |
| Mất cả nhóm `rg-dr-primary` | Chuyển lạnh với `DR_IMAGES_FROM_COPY=true`, hoặc chuyển ấm | như hai dòng trên |

## Các bước khôi phục

1. Phát hiện: ghi giờ sự cố (UTC).
2. Quyết định: người quyết định gửi tin "bắt đầu sự cố" (mẫu ở dưới).
3. Khôi phục, chọn một trong ba cách:
   - Mất namespace: `bash scripts/azure/restore-namespace.sh <run_id> <giờ sự cố trừ 1 giây, dạng 2026-10-31T09:27:16Z>`. Script chọn bản Velero mới nhất của phiên đang chạy, dựng lại cơ sở dữ liệu về đúng thời điểm, tạo lại lịch backup và lấy ngay một bản đầy đủ. Vòng thử: 64 giây.
   - Chuyển lạnh: `bash scripts/azure/failover-cold.sh <run_id> standby` (thêm `DR_IMAGES_FROM_COPY=true` ở đầu lệnh khi kho ảnh chính đã mất). Script chạy ba bước `infra`, `restore`, `switch`: dựng máy, cài phần mềm và khôi phục cơ sở dữ liệu từ kho ở Nhật, lấy một bản đầy đủ, gỡ chính sách chép ảnh và chờ kho ảnh dự phòng nhận ghi, rồi đổi DNS. Vòng thử: dựng máy 113 đến 138 giây, khôi phục 266 đến 277 giây, đổi DNS 12 đến 17 giây.
   - Chuyển ấm: `bash scripts/azure/failover-warm.sh <run_id>`. Script nâng cụm bản sao thành cụm chính, tạo lịch backup, gỡ chính sách chép ảnh, bật ghi ảnh, khởi động lại API, lấy một bản đầy đủ, rồi đổi DNS. Vòng thử: 215 giây cho khôi phục, 11 giây đổi DNS.
4. Nếu máy ảo mới kẹt ở trạng thái `starting` quá 10 phút: `az vm delete -g rg-dr-standby -n vm-dr-standby --yes --force-deletion true`, rồi `az disk delete -g rg-dr-standby -n vm-dr-standby-os --yes`, rồi chạy lại lệnh chuyển lạnh. Vòng thử gặp một lần, Azure trả `VMStartTimedOut` sau 41 phút.
5. Kiểm tra theo `checklist-khoi-phuc.md`. Khi chạy bằng `azure_drill`, bước `verify` tự so số bài với sổ ghi, so mã băm nội dung, tải lại từng ảnh và thử đăng một bài mới.
6. Gửi tin "đã chuyển sang dự phòng" khi DNS đã đổi, rồi "đã khôi phục xong" khi kiểm tra đạt.

## Liên lạc trong lúc sự cố

Gửi vào nhóm Zalo của đồ án, mỗi tin ghi giờ gửi:

- Bắt đầu sự cố: `[<giờ>] Web DR gặp sự cố: <mô tả ngắn>. <người quyết định> đã kích hoạt khôi phục theo cách <tại chỗ/lạnh/ấm>.`
- Đã chuyển sang dự phòng: `[<giờ>] api.dr.qivarn.id.vn đã trỏ sang cụm <tên cụm>. Đang kiểm tra dữ liệu.`
- Đã khôi phục xong: `[<giờ>] Đã khôi phục xong. Thời gian ngừng <số phút> phút, mất <số bài> bài gần nhất.`

## Dựng lại sau diễn tập

Sau khi chuyển sang `standby`, đưa hệ thống về trạng thái ban đầu theo thứ tự:

1. Xóa ổ đĩa mồ côi của máy chính nếu còn: `az disk delete -g rg-dr-primary -n vm-dr-primary-os --yes`.
2. `bash scripts/azure/session-stop.sh standby` (lấy bản đầy đủ và bản Velero rồi xóa máy dự phòng).
3. `bash scripts/azure/session-start.sh primary main`.
4. `bash scripts/azure/restore-replication.sh`: dựng lại chính sách chép ảnh sang kho dự phòng. Chỉ chạy sau bước 3; chạy khi cụm dự phòng đang phục vụ sẽ làm kho ảnh dự phòng thành chỉ đọc.
5. `bash scripts/azure/reset-seed.sh primary`: đưa cơ sở dữ liệu về bộ mẫu 1.026 bài và làm mới sổ ghi bài.
6. Với tình huống chuyển ấm, thêm `bash scripts/azure/standby-up.sh main`.

Hết buổi thì tắt hết: `session-stop.sh <cụm đang phục vụ>`, `standby-down.sh` nếu còn cụm dự phòng, rồi kiểm tra `az vm list` không còn máy `vm-dr-*`.

## Chỗ để khóa

Khóa và mã bí mật nằm trong `~/.dr/` trên máy người chạy, không nằm trong kho mã: khóa SSH, kubeconfig từng cụm, khóa tài khoản lưu trữ, mã đăng bài, token Cloudflare, email ngân sách (`budget-email`). Lệnh nào cần thì tự đọc từ đó, không in ra màn hình.

## Lịch sử thay đổi

| Ngày | Sau lần diễn tập | Thay đổi |
|---|---|---|
| 31/10/2026 | trial-D1-1 | Lấy bản đầy đủ ngay khi có server Postgres mới; bật phiên lấy thêm bản Velero; khôi phục namespace chỉ từ bản Velero của phiên đang chạy |
| 31/10/2026 | trial-D1-2 | Sửa câu jsonpath chọn bản Velero |
| 31/10/2026 | trial-D2-1 | Thêm bước xử lý máy ảo kẹt ở `starting` và ổ đĩa còn sót |
| 31/10/2026 | trial-D2-2 | Gỡ chính sách chép ảnh theo ID đầy đủ, chờ kho ảnh dự phòng nhận ghi |
| 31/10/2026 | trial-D2-3 | Thêm `restore-replication.sh` vào bước dựng lại |
| 31/10/2026 | trial-D3-1 | Chuyển ấm tạo lại lịch backup đầy đủ và lịch Velero |
