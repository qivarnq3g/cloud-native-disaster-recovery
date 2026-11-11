# Bài thuyết trình đề tài 23, nói cùng video

Video: https://youtu.be/iPRazYU_bQM (10 phút 30 giây, không tiếng), chạy liền một mạch, không cần dừng.

## Khác gì bản đọc theo video

Bản đọc cũ tả lại màn hình: "Đây là lúc sự cố", "Velero báo sẵn sàng". Người xem tự thấy những điều đó rồi.

Bản này nói điều màn hình không nói được: vì sao làm vậy, điều đó chứng minh gì, và người nghe nên nhớ gì. Mỗi phần có ba nhịp:

1. Câu hỏi hoặc vấn đề, để người nghe tò mò.
2. Video cho thấy câu trả lời; người nói chỉ vào chỗ quan trọng.
3. Câu chốt: "điều này có nghĩa là...".

Mắt nhìn người nghe, không nhìn màn hình. Chỉ liếc màn hình khi nói "các bạn để ý...".

Thời lượng mỗi đoạn tính theo tốc độ nói khoảng 3 tiếng mỗi giây. Nói chậm hơn cũng được: bỏ bớt câu trong ngoặc vuông.

## Trước khi bấm chạy video (Thư, khoảng 30 giây, không tính giờ video)

"Em chào thầy và các bạn. Em xin hỏi một câu: trường mình có nội quy phòng cháy, nhưng nếu chưa bao giờ diễn tập, thì khi cháy thật, mọi người có thoát ra kịp không? Chưa ai biết. Hệ thống trên mây cũng vậy. Công ty nào cũng có kế hoạch khôi phục khi sập, nhưng kế hoạch đó có dùng được không thì phải thử mới biết. Nhóm 23 đã thử. Mời thầy và các bạn xem."

## Thư: mở đầu (0:00-0:45)

0:00-0:22 · Tên đề tài, câu hỏi nghiên cứu

"Đề tài của nhóm là diễn tập khôi phục cho một trang web đăng ảnh trên Azure. Câu hỏi rất đơn giản: kế hoạch viết trên giấy, khi sự cố thật xảy ra, có cứu được web kịp không? Nhóm không đoán. Nhóm phá thật, rồi bấm giờ."

0:22-0:45 · Ba con số

"Muốn biết kịp hay không thì phải có thước đo. Nhóm dùng hai thước đo. Thứ nhất, web sập bao lâu thì phải chạy lại, gọi là RTO. Thứ hai, được phép mất bao nhiêu dữ liệu, gọi là RPO. Các bạn để ý ba con số trên màn hình: sáu mươi phút, mười phút, năm phút. Đây là ba mục tiêu mà cả bài sẽ kiểm tra."

## Hương: thiết kế (0:45-2:15)

0:45-1:03 · Bảng ảnh hưởng

"Nhưng những con số đó từ đâu ra? Nhóm hỏi: mất phần nào thì hỏng gì? Mất cơ sở dữ liệu là nặng nhất, vì không ai đọc hay đăng bài được nữa. Nên phần này được bảo vệ kỹ nhất."

1:03-1:25 · Kiến trúc

"Nguyên tắc của nhóm là: đừng để trứng trong một giỏ. Web chạy ở Hàn Quốc, nhưng bản sao được cất ở ba nơi khác nhau. Các bạn để ý: mỗi nơi chống một loại sự cố khác nhau, nên mất một nơi thì vẫn còn hai."

1:25-1:47 · Sao lưu mỗi phút, két chống xóa

"Vì sao RPO chỉ năm phút? Vì mọi thay đổi trong cơ sở dữ liệu được gửi sang Nhật ít nhất mỗi phút. Còn nếu kẻ gian chiếm được tài khoản và muốn xóa hết bản sao? Nhóm có một két mà bảy ngày không ai xóa được, kể cả quản trị viên."

1:47-2:15 · Bảy kịch bản

"Rồi nhóm tự hỏi: hệ thống có thể hỏng theo những kiểu nào? Nhóm liệt kê bảy kiểu, từ nhẹ đến nặng: lỡ tay xóa nhầm, cháy một máy, mất cả khu, kẻ gian phá két, và mất cả tài khoản Azure. Mỗi kiểu được bấm giờ qua năm bước, để biết chậm ở đâu. Bây giờ, Quang sẽ cho thầy và các bạn xem nhóm phá thật."

## Quang: phá thật (2:15-8:30)

### Hệ thống trước khi phá (2:15-3:30)

2:15-2:41 · Hệ thống đang chạy

"Trước khi phá, phải chắc là hệ thống đang khỏe. Đây là bản chạy thử trên một máy, cùng ứng dụng và cùng cách sao lưu như trên Azure. [Nhóm dùng bản này vì nó nhanh và miễn phí, chạy được ba mươi lần mỗi kịch bản.] Các bạn để ý dòng ok: web đang chạy bình thường."

2:43-3:15 · Dữ liệu và sao lưu

"Trong web đã có một nghìn bài kèm ảnh. Đây là thứ nhóm phải giữ. Các dòng tiếp theo cho thấy bản sao lưu đã sẵn sàng: dữ liệu đã được chụp đầy đủ, và mọi thay đổi mới được gửi đi mỗi phút. Nghĩa là nếu sập ngay bây giờ, nhóm mất nhiều nhất khoảng một phút dữ liệu."

3:17-3:30 · Cụm dự phòng

"Và đây là máy dự phòng, đang chạy sẵn và nhận dữ liệu liên tục. Các bạn nhớ nó, lát nữa nó sẽ cứu cả hệ thống."

### D1: lỡ tay xóa nhầm (3:30-6:00)

3:30-3:45 · Tiêu đề

"Sự cố đầu tiên là sự cố hay gặp nhất ngoài đời: con người lỡ tay. Người vận hành gõ nhầm một lệnh và xóa mất toàn bộ ứng dụng."

3:45-4:09 · Trước sự cố, sự cố

"Để giống thật, trong lúc phá vẫn có người dùng đăng bài, mỗi giây một bài. Và đây, ứng dụng bị xóa. [Lúc này, với người dùng, web đã biến mất.]"

4:10-4:35 · Phát hiện, khôi phục

"Mười hai giây sau, hệ thống tự phát hiện. Sau đó nó làm hai việc: dựng lại cấu hình của ứng dụng, rồi lấy bản chụp đầy đủ và ghi tiếp các thay đổi, đến sát giây trước sự cố. [Giống như chép lại cuốn sổ từ bản photo, rồi viết thêm những dòng mới.]"

4:36-4:57 · Kiểm tra

"Nhưng chạy lại thôi thì chưa đủ. Câu hỏi quan trọng là: dữ liệu có còn đúng không? Nên công cụ đếm từng bài, so từng ảnh, và đăng thử một bài mới."

4:59-5:19 · Kết quả 1096/1096

"Kết quả: một nghìn không trăm chín mươi sáu bài, không thiếu bài nào, không hỏng ảnh nào."

5:19-6:00 · Ba thẻ RTO

"Và mất bao lâu? Năm mươi lăm giây. Một lần nhanh có thể là may mắn, nên nhóm chạy ba mươi lần: lần nào cũng khoảng một phút. Trên Azure thật cũng chỉ khoảng một phút mười lăm giây. Điều này có nghĩa là: lỡ tay xóa nhầm, người dùng chỉ thấy web gián đoạn khoảng một phút."

### D3: cháy máy, dùng dự phòng ấm (6:00-7:45)

6:00-6:32 · Cụm chính sập

"Nhưng nếu không phải lỡ tay, mà là cả máy chủ biến mất thì sao? Máy, ổ đĩa, cấu hình, tất cả. Lúc này máy dự phòng lúc nãy vào cuộc. Nó đã chạy sẵn và có sẵn dữ liệu, nên không cần dựng gì cả, chỉ cần cho nó lên làm máy chính."

6:32-6:58 · Sự cố, nâng cụm

"Vẫn có người dùng đăng bài. Máy chính mất. Năm giây sau đã phát hiện, và máy dự phòng được nâng lên làm chính."

6:59-7:08 · RPO, đạt

"Các bạn để ý: lần này có mất ba mươi sáu bài cuối, vì chưa kịp chép sang. Nhưng đó chỉ là vài chục giây, vẫn trong mức năm phút cho phép."

7:08-7:45 · Kết quả, so với Azure

"Chỉ khoảng mười lăm giây, web đã chạy lại trên máy dự phòng. Trên Azure thật lâu hơn, khoảng bốn phút rưỡi, vì phải chờ kho ảnh, khởi động lại và đổi địa chỉ web. Nhưng vẫn dưới mục tiêu mười phút. Đây là cái giá của sự nhanh: phải trả tiền cho một máy chạy sẵn suốt ngày đêm."

### D6: kẻ gian phá két (7:45-8:30)

7:45-7:57 · Tiêu đề

"Kịch bản cuối của phần này đáng sợ nhất: kẻ gian, hay mã độc tống tiền, chiếm được quyền cao nhất và muốn xóa sạch bản sao lưu, để nạn nhân không còn đường lui."

7:58-8:28 · Bị từ chối

"Nhóm thử mọi cách: xóa, bỏ qua khóa, rút ngắn thời hạn, xóa cả két. Các bạn thấy đấy: tất cả đều bị từ chối. Ghi đè cũng chỉ tạo ra bản mới, bản gốc vẫn còn. Nghĩa là dù mất quyền quản trị, dữ liệu vẫn an toàn. Tiếp theo, Thư sẽ trình bày kết quả trên Azure thật."

## Thư: kết quả trên Azure (8:30-10:00)

8:30-8:52 · Vòng thử

"Đây là phần nhóm thấy quan trọng nhất. Lần đầu chạy trên Azure, bảy trên mười hai lần thất bại. Kế hoạch đọc thì thấy ổn, nhưng chạy thật thì máy ảo bị kẹt, hay một cài đặt cũ còn sót chặn việc chép ảnh. Những lỗi này không ai thấy được nếu chỉ đọc giấy."

8:52-9:16 · Vòng chính thức

"Nhóm sửa từng lỗi rồi chạy lại. Lần này mười lăm trên mười bảy lần đạt. Dựng máy mới lâu nhất khoảng mười một phút, mục tiêu là sáu mươi. Dùng máy dự phòng lâu nhất khoảng bốn phút rưỡi, mục tiêu là mười. [Hai lần không đạt là do công cụ kiểm tra bị treo, nhưng nhóm vẫn tính là không đạt.]"

9:16-9:38 · Điểm nghẽn

"Vậy chậm ở đâu? Biểu đồ cho thấy: phần lớn thời gian là khôi phục dữ liệu, nhất là chép ảnh từ Nhật về. Muốn nhanh hơn thì phải cải tiến đúng bước này, chứ không phải bước khác."

9:38-10:00 · Két và máy chủ ngoài Azure

"Và trường hợp tệ nhất, mất cả tài khoản Azure? Nhóm vẫn lấy được dữ liệu từ máy chủ bên ngoài, khôi phục đủ một nghìn không trăm hai mươi sáu bài trong chưa đầy một phút."

## Hương: chi phí và kết luận (10:00-10:30)

10:00-10:16 · Chi phí

"Cuối cùng là tiền. Cả thử nghiệm chỉ tốn năm phẩy bảy đô. Dựng máy mới khi cần tốn khoảng một đô mỗi tháng, máy dự phòng chạy sẵn tốn khoảng bốn mươi bốn đô. Với web nhỏ như của nhóm, cách rẻ đã đạt mục tiêu, nên không cần trả thêm."

10:16-10:30 · Kết luận

"Quay lại câu hỏi ban đầu: kế hoạch trên giấy có cứu được web không? Câu trả lời của nhóm là: chưa, cho đến khi diễn tập và sửa lỗi. Cảm ơn thầy và các bạn đã lắng nghe."

## Sau video (Hương hoặc Quang, 10 giây)

"Nhóm em xin hết phần trình bày, mời thầy và các bạn đặt câu hỏi."
