# data

Số liệu đo thô dạng CSV/JSON của từng lần diễn tập. Mỗi tệp ghi rõ ngày, lần diễn tập và điều kiện đo.

`azure/cost-2026-11-08.csv`: chi phí thật của sáu nhóm tài nguyên `rg-dr-*`, đọc từ Azure Cost Management (ActualCost) ngày 08/11/2026, khoảng 25/09 đến hết 07/11/2026, đơn vị USD. Dòng `meter` theo đồng hồ tính tiền (làm tròn 3 chữ số, dòng dưới 0,005 USD bị bỏ), `group` theo nhóm tài nguyên, `day` theo ngày từ 29/10, `total` là tổng.
