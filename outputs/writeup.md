# Bài viết ngắn — Lab 25: GPU FinOps

**Học viên:** Nguyễn Thiên Lộc  
**MSHV:** 2A202601479  
**Lớp:** Cohort 3 · Track 2

## 1. Baseline và kết quả tối ưu

Bài làm dùng dữ liệu tổng hợp seed=25 và giá mô phỏng tháng 6/2026. Kết quả là ước tính theo code lab, không phải hóa đơn hay năng lượng đo trên GPU thực. Ngân sách M5 giảm từ **$27,133 xuống $14,626/tháng**, tiết kiệm **$12,507 (46.1%)**. Riêng inference M2 giảm **$6.488 → $1.126/1M-token (82.6%)**, giữ nguyên 7,533,027 input + output tokens. Hai tỷ lệ có mẫu số khác nhau, không cộng trực tiếp.

## 2. Biện pháp nào đóng góp nhiều nhất?

| Biện pháp | Tiết kiệm USD/tháng |
|---|---:|
| Inference: cascade/cache/batch | 1,212 |
| Purchasing: spot/reserved | 10,040 |
| Right-sizing theo giả định mẫu | 655 |
| Loại bỏ idle | 600 |

Purchasing đóng góp **80.3%** tổng savings vì giảm giá thuê trên lượng GPU-giờ lớn. Trong riêng M2, phân rã theo thứ tự cascade → cache → batch cho mức giảm lần lượt **$37.3985, $1.1965, $1.7946/ngày**; cascade chiếm 92.6%. Đóng góp biên phụ thuộc thứ tự, không phải hiệu quả độc lập. Model nhỏ cần được kiểm tra chất lượng; batch chỉ phù hợp khi chấp nhận chờ.

## 3. GPU-Util lie và tác động tài chính

M1 gắn cờ **gpu-h100-4 (util 98.2%, MFU 19.4%); gpu-a10g-1 (util 96.9%, MFU 26.8%)**. GPU có hoạt động không có nghĩa đang tận dụng FLOPs hiệu quả: kernel có thể chờ dữ liệu hoặc xử lý công việc quá nhỏ. Đây là giả thuyết cần profiler xác minh; MFU thấp cũng có thể do workload memory-bound. Không thể lấy 1 − MFU làm tỷ lệ hóa đơn cắt được. Idle gây lãng phí **$20/ngày = $600/30 ngày**. Khoản right-sizing $655/tháng chỉ có ý nghĩa khi GPU rẻ hơn vẫn đáp ứng VRAM, throughput và latency.

## 4. Hai extensions đã thực hiện

**Ex4 — Ngân sách reasoning:** nhóm này chiếm **8.375% request**, **16.46% tiền** và **94.04% năng lượng mô phỏng**. Trần 10% không tác động vì tỷ lệ hiện tại đã thấp hơn. Trần 5% chuyển 81 request sang thường, tiết kiệm **$0.2261/ngày (2.67%)** và **7879.63 Wh/ngày (24.88%)**. Mô phỏng giảm output 6 lần và bỏ hệ số năng lượng 80x; không áp hệ số 80x cho tiền. Đề xuất chỉ reasoning khi complexity >=0.8 và còn ngân sách; CSV chưa có score nên dùng độ dài output làm proxy offline. Chất lượng tương đương chưa được chứng minh.

**Ex5 — Chuyển vùng theo carbon:** 5 job interruptible dùng tổng **1,789 kWh** ước tính theo công suất catalog và số ngày riêng của mỗi job. Chuyển từ us-east-1 sang europe-north1 giảm **626.15 kg CO2e (92.11%)**, đồng thời giảm tiền điện **$53.67 (25%)**. europe-north1 sạch nhất; us-east-wa rẻ nhất và là lựa chọn rẻ nhất dưới ngưỡng 100 gCO2e/kWh. Phải kiểm tra độ trễ, egress, dữ liệu cư trú và GPU sẵn có. Các số này không phải savings theo tháng và không cộng vào tiền thuê GPU đã có thể bao gồm điện.

## 5. Ba hành động đầu tiên cho NimbusAI

1. **Kiểm soát idle và ownership:** đặt lịch thu hồi tài nguyên idle, hoàn thiện team/project tag và showback. Coverage hiện tại 91.8% vượt ngưỡng chargeback 80% của lab, nhưng vẫn cần xử lý phần thiếu tag trước khi tính phí nội bộ.
2. **Thử spot trước khi cam kết:** kiểm chứng checkpoint, khả năng khôi phục và deadline; chỉ mua reserved khi đủ bằng chứng về nhu cầu dài hạn. M3 dùng 30 ngày và policy hòa vốn đơn giản, chưa phản ánh đầy đủ nghĩa vụ trả tiền toàn kỳ cam kết.
3. **Đánh giá rồi mở rộng inference:** ưu tiên cascade, cache và batch có kiểm soát chất lượng; profile util-lie trước đổi GPU. Thử giới hạn reasoning và chuyển vùng như hai kịch bản riêng, theo dõi chất lượng, p95 latency, USD/1M-token và carbon.

**Giới hạn kết luận:** M5 cộng các bucket theo mẫu; chưa có mapping gpu_id → job_id để loại trừ cộng trùng hoặc xác nhận chi phí inference và GPU là hai hóa đơn riêng. Vì vậy 46.1% là tiềm năng mô phỏng, không phải savings đã kiểm toán. Bảng chi tiết và giả định nằm trong report.md; mã nguồn và tests mới cho phép tái tạo kết quả, tests gốc giữ nguyên.
