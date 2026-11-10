# Lời thuyết trình theo video

Video: https://youtu.be/iPRazYU_bQM (10 phút 30 giây, không có tiếng). Mỗi đoạn ghi mốc thời gian trong video, cảnh đang chiếu và lời nói. Lời được viết vừa với thời lượng nếu nói khoảng 3 tiếng mỗi giây. Chỗ ghi "(dừng)" thì để video tự chạy.

Đọc số: 55,7 s đọc là "năm mươi lăm phẩy bảy giây". RTO (thời gian khôi phục) và RPO (lượng dữ liệu được phép mất) đọc nguyên chữ cái.

Phân công:

- Thư: 0:00-0:45 và 8:30-10:00
- Hương: 0:45-2:15 và 10:00-10:30
- Quang: 2:15-8:30

## Thư: mở đầu (0:00-0:45)

0:00-0:08 · Tên đề tài

"Nhóm 23 xin trình bày đề tài: diễn tập khôi phục sau thảm họa cho một web ảnh chạy trên Azure."

0:08-0:22 · Câu hỏi nghiên cứu

"Câu hỏi của nhóm là: kế hoạch khôi phục viết trên giấy có đạt mục tiêu khi gặp sự cố thật không? Chưa diễn tập thì chưa biết. Nên nhóm dựng hệ thống, phá thật, rồi đo."

0:22-0:45 · Ba con số phải đạt

"Nhóm đặt ba con số. RTO là thời gian từ lúc sự cố đến lúc web chạy lại. Với cách lạnh, tức là dựng cụm mới từ bản sao lưu, RTO tối đa sáu mươi phút. Với cách ấm, chuyển sang cụm dự phòng đang chạy sẵn, tối đa mười phút. Còn RPO, lượng dữ liệu được phép mất, tối đa năm phút."

## Hương: phân tích và thiết kế (0:45-2:15)

0:45-1:03 · Bảng ảnh hưởng khi web ngừng

"Trước khi đặt mục tiêu, nhóm phân tích ảnh hưởng khi web ngừng. Mất cơ sở dữ liệu thì không đọc, không đăng được bài. Mất kho ảnh thì bài hiện mà ảnh lỗi. Cả trang ngừng thì người dùng không vào được."

1:03-1:25 · Kiến trúc

"Về kiến trúc, ứng dụng chạy trên một cụm Kubernetes ở Hàn Quốc. Bản sao được giữ ở ba nơi: kho sao lưu ở Nhật Bản, một két chỉ ghi cũng ở Nhật, và một server nằm ngoài Azure. Mất một nơi thì vẫn còn hai nơi."

1:25-1:47 · Sao lưu mỗi phút, két chỉ ghi

"Cơ sở dữ liệu đẩy nhật ký thay đổi, gọi là WAL, sang nước khác ít nhất mỗi phút. Dữ liệu còn được chép vào két chỉ ghi: giữ bảy ngày, không ai xóa hay sửa được, kể cả quản trị viên."

1:47-2:15 · Bảy kịch bản và năm bước đo

"Nhóm viết bảy kịch bản diễn tập, từ D1 đến D7: xóa nhầm namespace, mất cụm chính, mất cả nhóm tài nguyên, thử xóa két, và mất cả tài khoản Azure. RTO được chia thành năm bước: phát hiện, quyết định, dựng hạ tầng, khôi phục dữ liệu và đổi DNS. Sau khôi phục, công cụ so số bài và mã băm từng ảnh."

## Quang: chạy thử trên bản thu nhỏ (2:15-8:30)

### Hệ thống đang chạy (2:15-3:30)

2:15-2:23 · Tiêu đề "Hệ thống đang chạy"

"Đây là bản thu nhỏ chạy trên một máy, cùng ứng dụng và cùng cách sao lưu như trên Azure."

2:23-2:31 · Chú thích "Cụm chính"

"Cụm chính đang chạy cả ứng dụng lẫn cơ sở dữ liệu."

2:33-2:41 · Chú thích "/healthz"

"Gọi trang kiểm tra healthz, hệ thống trả về ok."

2:43-2:52 · Chú thích "Dữ liệu"

"Dữ liệu đã có sẵn một nghìn bài, mỗi bài kèm ảnh."

2:54-3:04 · Chú thích "CNPG"

"Bản sao lưu đầy đủ đã xong. Nhật ký WAL được đẩy đi ít nhất mỗi phút, nên nếu sập thì chỉ mất khoảng một phút dữ liệu."

3:06-3:15 · Chú thích "Velero"

"Velero, công cụ sao lưu cấu hình Kubernetes, báo kho sao lưu sẵn sàng."

3:17-3:30 · Chú thích "Cụm dự phòng"

"Còn cụm dự phòng đang chạy sẵn một bản sao cơ sở dữ liệu, dùng cho cách ấm ở phần sau."

### D1: xóa nhầm namespace (3:30-6:00)

3:30-3:45 · Tiêu đề "Xóa nhầm namespace"

"Tình huống lỗi đầu tiên, kịch bản D1: người vận hành xóa nhầm toàn bộ namespace của ứng dụng. Kịch bản vừa đăng bài, vừa phá, vừa đo từng bước."

3:45-4:00 · Chú thích "Trước sự cố"

"Trước sự cố, công cụ đăng một bài mỗi giây trong chín mươi giây. Phần này được tua nhanh."

4:02-4:09 · Chú thích "Sự cố"

"Đây là lúc sự cố: toàn bộ namespace bị xóa."

4:10-4:19 · Chú thích "Phát hiện", "Velero"

"Mười hai giây sau, healthz hỏng năm lần liền: sự cố được phát hiện. Velero khôi phục lại cấu hình."

4:19-4:35 · Chú thích "CNPG"

"CNPG dựng lại cơ sở dữ liệu từ bản sao lưu đầy đủ, rồi chạy tiếp nhật ký WAL đến sát lúc sự cố."

4:36-4:47 · Chú thích "Kiểm tra"

"Sau đó kiểm tra: đếm bài, so nội dung, tải từng ảnh so mã băm, và đăng thử một bài mới."

4:47-4:57 · Chú thích "Đạt"

"Kết quả đạt: không thiếu bài nào, mọi ảnh còn nguyên."

4:59-5:19 · Kết quả 1096/1096

"Một nghìn không trăm chín mươi sáu bài còn nguyên, RPO bằng không." (dừng)

5:19-5:45 · Ba thẻ RTO

"Lần quay này RTO là năm mươi lăm phẩy bảy giây. Ba mươi lần chạy trên bản thu nhỏ có trung vị năm mươi sáu phẩy chín giây. Trên Azure, trung vị là bảy mươi tư phẩy một giây. Mục tiêu là mười phút, nên D1 khôi phục trong khoảng một phút và lặp lại ổn định." (dừng đến 6:00)

### D3: mất cụm chính, cách ấm (6:00-7:45)

6:00-6:18 · Cảnh 3D "Cụm chính sập"

"Tình huống thứ hai, kịch bản D3: mất hẳn cụm chính. Máy chủ, ổ đĩa, cấu hình đều mất."

6:18-6:32 · Tiêu đề "Mất cụm chính"

"Cụm dự phòng đã chạy sẵn bản sao cơ sở dữ liệu, nên chỉ cần nâng nó lên làm cụm chính. Đây là cách ấm."

6:32-6:42 · Chú thích "Trước sự cố"

"Vẫn đăng một bài mỗi giây trong chín mươi giây, phần này tua nhanh."

6:44-6:52 · Chú thích "Sự cố", "Phát hiện"

"Cụm chính mất hẳn. Năm giây sau đã phát hiện."

6:53-6:58 · Chú thích "Nâng cụm"

"Cơ sở dữ liệu ở cụm dự phòng được nâng lên làm cụm chính."

6:59-7:08 · Chú thích "RPO", "Đạt"

"Ba mươi sáu bài cuối chưa kịp chép sang, vẫn trong mức năm phút. RTO mười bốn phẩy tám giây, ảnh không hỏng."

7:08-7:25 · Cảnh 3D "Cụm dự phòng lên thay"

"Như vậy chỉ sau mười lăm giây, web đã chạy lại trên cụm dự phòng, không mất ảnh nào."

7:25-7:45 · So sánh với Azure

"Trên bản thu nhỏ, trung vị là mười ba phẩy bảy giây. Trên Azure là hai trăm sáu mươi lăm giây, chủ yếu ở bước nâng cụm dự phòng, khoảng hai trăm mười lăm giây, và đổi DNS."

### D6: thử phá két (7:45-8:30)

7:45-7:57 · Tiêu đề "Thử phá két"

"Kịch bản D6: thử phá két. Két bật khóa ghi một lần, giữ bảy ngày. Nhóm tải một gói sao lưu vào rồi dùng cả khóa quản trị để phá."

7:58-8:13 · Năm dòng "bị từ chối"

"Xóa phiên bản: bị từ chối. Bỏ qua khóa quản trị: bị từ chối. Rút ngắn thời hạn giữ: bị từ chối. Xóa bằng khóa ghi, xóa cả két: đều bị từ chối."

8:14-8:28 · Chú thích "Ghi đè", "Đạt"

"Ghi đè thì chỉ tạo ra phiên bản mới, bản gốc vẫn còn nguyên. Không cách nào làm mất bản gốc."

## Thư: kết quả trên Azure (8:30-10:00)

8:30-8:52 · Bảy lần hỏng ở vòng thử

"Tiếp theo là kết quả trên Azure. Ở vòng thử, có bảy lần không đạt. Mỗi lần lộ ra một lỗi thật, như Velero lấy bản sao lưu cũ, máy ảo bị kẹt, hay chính sách chép ảnh chặn ghi. Lỗi nào cũng được sửa trước vòng chính thức."

8:52-9:16 · Vòng chính thức 15 trên 17 lần đạt

"Sau khi sửa, vòng chính thức đạt mười lăm trên mười bảy lần. RTO cách lạnh lớn nhất khoảng mười một phút, mục tiêu là sáu mươi phút. Cách ấm lớn nhất hơn bốn phút một chút, mục tiêu mười phút. Hai lần không đạt là do công cụ kiểm tra bị treo, không phải do khôi phục."

9:16-9:38 · Điểm nghẽn

"Chia theo từng bước thì điểm nghẽn là khôi phục dữ liệu. Ở D4, riêng bước này mất hơn bảy phút trên tổng mười phút, chủ yếu là chép ảnh từ Nhật. Cách ấm bỏ được bước dựng máy, nhưng vẫn còn khoảng ba phút rưỡi khôi phục."

9:38-10:00 · Két và server ngoài Azure

"Két từ chối mọi cách xóa. Khi mất cả tài khoản Azure, server bên ngoài vẫn khôi phục được một nghìn không trăm hai mươi sáu bài trong năm mươi chín giây. Trên bản thu nhỏ, cả một trăm mười chín lần chạy đều đạt."

## Hương: chi phí và kết luận (10:00-10:30)

10:00-10:16 · Chi phí, lạnh hay ấm

"Toàn bộ thử nghiệm tốn năm phẩy bảy đô la. Cách lạnh tốn khoảng một đô mỗi tháng và đã đạt mục tiêu. Cách ấm tốn khoảng bốn mươi bốn đô mỗi tháng."

10:16-10:30 · Kết luận

"Kết luận: kế hoạch chỉ đạt mục tiêu sau khi đã diễn tập và sửa lỗi. Bước tiếp theo là diễn tập không báo trước. Cảm ơn thầy và các bạn đã lắng nghe."
