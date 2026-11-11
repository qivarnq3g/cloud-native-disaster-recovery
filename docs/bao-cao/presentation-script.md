# Lời thuyết trình theo video

Video: https://youtu.be/iPRazYU_bQM (10 phút 30 giây, không có tiếng). Mỗi đoạn ghi mốc thời gian trong video, cảnh đang chiếu và lời nói. Lời được viết vừa với thời lượng nếu nói khoảng 3 tiếng mỗi giây. Chỗ ghi "(dừng)" thì để video tự chạy. Dòng "Hiểu" giải thích ý cho người nói, không đọc ra.

Đọc số: 55,7 s đọc là "năm mươi lăm phẩy bảy giây". RTO (thời gian khôi phục) và RPO (lượng dữ liệu được phép mất) đọc nguyên chữ cái: "a-ti-ô", "a-pi-ô".

Phân công:

- Thư: 0:00-0:45 và 8:30-10:00
- Hương: 0:45-2:15 và 10:00-10:30
- Quang: 2:15-8:30

## Thư: mở đầu (0:00-0:45)

0:00-0:08 · Tên đề tài

"Nhóm 23 xin trình bày đề tài: diễn tập khôi phục sau thảm họa cho một web đăng ảnh chạy trên Azure."

0:08-0:22 · Câu hỏi nghiên cứu

"Câu hỏi của nhóm là: kế hoạch khôi phục viết trên giấy có dùng được khi gặp sự cố thật không? Giống nội quy phòng cháy, chưa diễn tập thì chưa biết. Nên nhóm dựng hệ thống, phá thật, rồi bấm giờ."

0:22-0:45 · Ba con số phải đạt

"Nhóm đặt ba con số. RTO là thời gian web được phép ngừng. Nếu dựng máy mới từ bản sao lưu, gọi là dự phòng nguội, tối đa sáu mươi phút. Nếu chuyển sang máy dự phòng đang chạy sẵn, gọi là dự phòng ấm, tối đa mười phút. Còn RPO, lượng dữ liệu được phép mất, tối đa năm phút."

Hiểu: RPO là phần mất, từ lần lưu cuối đến lúc sự cố. RTO là thời gian chờ, từ lúc sự cố đến lúc chạy lại.

## Hương: phân tích và thiết kế (0:45-2:15)

0:45-1:03 · Bảng ảnh hưởng khi web ngừng

"Trước khi đặt mục tiêu, nhóm xem mất phần nào thì hỏng gì. Mất cơ sở dữ liệu thì không đọc, không đăng được bài. Mất kho ảnh thì bài hiện mà ảnh lỗi. Cả trang ngừng thì người dùng không vào được."

1:03-1:25 · Kiến trúc

"Ứng dụng chạy trên một cụm máy chủ ở Hàn Quốc. Bản sao được cất ở ba nơi: kho sao lưu ở Nhật, một két chống xóa cũng ở Nhật, và một máy chủ nằm ngoài Azure. Mất một nơi thì vẫn còn hai nơi."

Hiểu: cụm là nhóm máy chạy Kubernetes, phần mềm tự chạy và quản lý ứng dụng. Ở đây cụm chỉ có một máy ảo.

1:25-1:47 · Sao lưu mỗi phút, két chống xóa

"Cơ sở dữ liệu ghi mọi thay đổi vào một nhật ký, gọi là WAL, và gửi nhật ký sang Nhật ít nhất mỗi phút. Dữ liệu còn được cất vào két chống xóa: bảy ngày không ai xóa hay sửa được, kể cả quản trị viên."

Hiểu: két là một kho lưu trữ tệp của Azure bật khóa WORM (ghi một lần, chỉ đọc). Không phải server.

1:47-2:15 · Bảy kịch bản và năm bước đo

"Nhóm viết bảy kịch bản diễn tập, từ nhẹ đến nặng: xóa nhầm ứng dụng, mất máy chủ, mất cả nhóm tài nguyên, thử phá két, và mất cả tài khoản Azure. Thời gian được bấm qua năm bước: phát hiện, quyết định, dựng hạ tầng, khôi phục dữ liệu và đổi tên miền. Xong thì đếm bài và so từng ảnh."

Hiểu: D1 xóa nhầm; D2, D3 mất máy chủ (nguội, ấm); D4, D5 mất cả nhóm tài nguyên, tức cả máy chủ lẫn kho ảnh (nguội, ấm); D6 phá két; D7 mất tài khoản Azure.

## Quang: chạy thử trên một máy (2:15-8:30)

### Hệ thống đang chạy (2:15-3:30)

2:15-2:23 · Tiêu đề "Hệ thống đang chạy"

"Đây là bản chạy thử trên một máy, cùng ứng dụng và cùng cách sao lưu như trên Azure."

Hiểu: bản chạy thử dùng kind, một Kubernetes chạy gọn trong một máy, chạy trên máy của GitHub. Nhanh và miễn phí nên chạy được 30 lần mỗi kịch bản.

2:23-2:31 · Chú thích "Cụm chính"

"Cụm chính đang chạy cả ứng dụng lẫn cơ sở dữ liệu."

2:33-2:41 · Chú thích "/healthz"

"Gọi trang kiểm tra sức khỏe healthz, hệ thống trả về ok."

Hiểu: healthz là một địa chỉ của web chỉ để hỏi "còn sống không". Trả ok là web đang chạy.

2:43-2:52 · Chú thích "Dữ liệu"

"Dữ liệu đã có sẵn một nghìn bài, mỗi bài kèm ảnh."

2:54-3:04 · Chú thích "CNPG"

"CNPG, công cụ quản lý cơ sở dữ liệu, đã sao lưu đầy đủ. Nhật ký WAL gửi đi ít nhất mỗi phút, nên sập thì chỉ mất tối đa khoảng một phút."

3:06-3:15 · Chú thích "Velero"

"Velero, công cụ sao lưu cấu hình của ứng dụng, báo kho sao lưu sẵn sàng."

Hiểu: CNPG lo phần dữ liệu (bài viết). Velero lo phần cấu hình, tức các tệp mô tả ứng dụng chạy thế nào.

3:17-3:30 · Chú thích "Cụm dự phòng"

"Còn cụm dự phòng đang chạy sẵn một bản sao cơ sở dữ liệu, nhận dữ liệu liên tục, dùng cho dự phòng ấm ở phần sau."

### D1: xóa nhầm namespace (3:30-6:00)

3:30-3:45 · Tiêu đề "Xóa nhầm namespace"

"Kịch bản đầu tiên, D1: người vận hành xóa nhầm namespace, tức cả ngăn chứa ứng dụng. Công cụ vừa đăng bài, vừa phá, vừa bấm giờ."

Hiểu: namespace giống một thư mục trong cụm, chứa web, API và cơ sở dữ liệu. Xóa nó là mất cả ứng dụng nhưng máy vẫn còn.

3:45-4:00 · Chú thích "Trước sự cố"

"Trước sự cố, công cụ đăng một bài mỗi giây trong chín mươi giây, như có người dùng thật. Phần này tua nhanh."

4:02-4:09 · Chú thích "Sự cố"

"Đây là lúc sự cố: cả namespace bị xóa."

4:10-4:19 · Chú thích "Phát hiện", "Velero"

"Mười hai giây sau, healthz hỏng năm lần liền: sự cố được phát hiện. Velero dựng lại cấu hình."

4:19-4:35 · Chú thích "CNPG"

"CNPG dựng lại cơ sở dữ liệu từ bản sao lưu đầy đủ, rồi chạy lại nhật ký WAL đến sát lúc sự cố."

Hiểu: bản đầy đủ giống ảnh chụp cuốn sổ lúc trước; WAL là các dòng ghi thêm sau đó. Chép bản đầy đủ rồi ghi tiếp các dòng là về đúng lúc trước sự cố.

4:36-4:47 · Chú thích "Kiểm tra"

"Sau đó kiểm tra: đếm bài, so nội dung, so từng ảnh bằng mã băm, và đăng thử một bài mới."

Hiểu: mã băm giống dấu vân tay của tệp. Ảnh hỏng dù một chút thì mã băm khác.

4:47-4:57 · Chú thích "Đạt"

"Kết quả đạt: không thiếu bài nào, mọi ảnh còn nguyên."

4:59-5:19 · Kết quả 1096/1096

"Một nghìn không trăm chín mươi sáu bài còn nguyên, không mất dữ liệu nào." (dừng)

5:19-5:45 · Ba thẻ RTO

"Lần quay này RTO là năm mươi lăm phẩy bảy giây. Ba mươi lần chạy thử có trung vị năm mươi sáu phẩy chín giây. Trên Azure, trung vị là bảy mươi tư phẩy một giây. Nghĩa là D1 khôi phục trong khoảng một phút, lần nào cũng gần như nhau." (dừng đến 6:00)

Hiểu: trung vị là số đứng giữa khi xếp các lần từ nhanh đến chậm. Dùng trung vị vì một lần quá chậm không kéo lệch kết quả.

### D3: mất cụm chính, dự phòng ấm (6:00-7:45)

6:00-6:18 · Cảnh 3D "Cụm chính sập"

"Kịch bản thứ hai, D3: mất hẳn cụm chính. Máy chủ, ổ đĩa, cấu hình đều mất."

6:18-6:32 · Tiêu đề "Mất cụm chính"

"Cụm dự phòng đã chạy sẵn bản sao cơ sở dữ liệu, nên chỉ cần nâng nó lên làm chính. Đây là dự phòng ấm."

6:32-6:42 · Chú thích "Trước sự cố"

"Vẫn đăng một bài mỗi giây trong chín mươi giây, phần này tua nhanh."

6:44-6:52 · Chú thích "Sự cố", "Phát hiện"

"Cụm chính mất hẳn. Năm giây sau đã phát hiện."

6:53-6:58 · Chú thích "Nâng cụm"

"Cơ sở dữ liệu ở cụm dự phòng được nâng lên làm chính."

6:59-7:08 · Chú thích "RPO", "Đạt"

"Ba mươi sáu bài cuối chưa kịp chép sang, vẫn trong mức năm phút. RTO mười bốn phẩy tám giây, ảnh không hỏng."

Hiểu: bản sao ở cụm dự phòng chạy chậm hơn bản chính vài giây, nên mấy bài cuối chưa kịp sang. Mất 36 bài trong vài chục giây vẫn dưới mức 5 phút cho phép.

7:08-7:25 · Cảnh 3D "Cụm dự phòng lên thay"

"Như vậy chỉ sau khoảng mười lăm giây, web đã chạy lại trên cụm dự phòng, không hỏng ảnh nào."

7:25-7:45 · So sánh với Azure

"Ở bản chạy thử, trung vị là mười ba phẩy bảy giây. Trên Azure là hai trăm sáu mươi lăm giây, phần lớn ở bước khôi phục dữ liệu, khoảng hai trăm mười lăm giây, còn lại là phát hiện và đổi tên miền."

Hiểu: trên Azure chậm hơn vì phải gỡ chính sách chép ảnh, chờ kho ảnh nhận ghi, khởi động lại API và đổi tên miền thật. Bản chạy thử không có mấy bước đó, nên không so trực tiếp.

### D6: thử phá két (7:45-8:30)

7:45-7:57 · Tiêu đề "Thử phá két"

"Kịch bản D6: thử phá két chống xóa. Két khóa bảy ngày. Nhóm bỏ một gói sao lưu vào rồi dùng cả khóa quản trị để phá."

7:58-8:13 · Năm dòng "bị từ chối"

"Xóa phiên bản: bị từ chối. Bỏ qua khóa quản trị: bị từ chối. Rút ngắn thời hạn khóa: bị từ chối. Xóa bằng khóa ghi, xóa cả két: đều bị từ chối."

8:14-8:28 · Chú thích "Ghi đè", "Đạt"

"Ghi đè thì chỉ tạo ra phiên bản mới, bản gốc vẫn nguyên. Không cách nào làm mất bản gốc."

Hiểu: D6 chứng minh kẻ gian có chiếm được tài khoản, hay mã độc tống tiền muốn xóa bản sao, thì bản trong két vẫn còn.

## Thư: kết quả trên Azure (8:30-10:00)

8:30-8:52 · Bảy lần hỏng ở vòng thử

"Tiếp theo là kết quả trên Azure. Ở vòng thử, bảy trên mười hai lần không đạt. Mỗi lần lộ ra một lỗi thật, như lấy nhầm bản sao lưu cũ, máy ảo bị kẹt, hay cài đặt cũ chặn chép ảnh. Lỗi nào cũng được sửa trước vòng chính thức."

8:52-9:16 · Vòng chính thức 15 trên 17 lần đạt

"Sau khi sửa, vòng chính thức đạt mười lăm trên mười bảy lần. Dự phòng nguội lâu nhất khoảng mười một phút, mục tiêu sáu mươi phút. Dự phòng ấm lâu nhất khoảng bốn phút rưỡi, mục tiêu mười phút. Hai lần không đạt là do công cụ kiểm tra bị treo, không phải do khôi phục."

9:16-9:38 · Điểm nghẽn

"Chia theo từng bước thì chậm nhất là khôi phục dữ liệu. Ở D4, riêng bước này mất hơn bảy phút trên tổng mười phút, chủ yếu là chép ảnh từ Nhật. Dự phòng ấm bỏ được bước dựng máy, nhưng vẫn còn khoảng ba phút rưỡi khôi phục."

9:38-10:00 · Két và máy chủ ngoài Azure

"Két từ chối mọi cách xóa. Khi mất cả tài khoản Azure, máy chủ bên ngoài vẫn khôi phục được một nghìn không trăm hai mươi sáu bài trong năm mươi chín giây. Ở bản chạy thử, cả một trăm mười chín lần đều đạt."

## Hương: chi phí và kết luận (10:00-10:30)

10:00-10:16 · Chi phí, nguội hay ấm

"Toàn bộ thử nghiệm tốn năm phẩy bảy đô la. Dự phòng nguội tốn khoảng một đô mỗi tháng và đã đạt mục tiêu. Dự phòng ấm tốn khoảng bốn mươi bốn đô mỗi tháng."

10:16-10:30 · Kết luận

"Kết luận: kế hoạch chỉ đạt mục tiêu sau khi đã diễn tập và sửa lỗi. Bước tiếp theo là diễn tập không báo trước. Cảm ơn thầy và các bạn đã lắng nghe."
