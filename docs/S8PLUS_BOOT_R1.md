# ALice S8+ boot R1 — bản thử nghiệm

Thiết bị: Galaxy S8+ Exynos 8895 / dream2lte, cùng ROM với boot ALice đã xuất.
Nền nguồn: alice-unified, commit 6b75fa2592ff7d98fd4dc929c09d1b6072a9ec25.
Mốc ESG1 trong repo: 45f0ebd745a50ac8d0a3b1fa78fa93c89de3e7c2.

## Thay đổi có trong boot

- Tắt MGLRU trong cấu hình build, như workflow ESG1. Bản trước bật cả
  CONFIG_LRU_GEN và CONFIG_LRU_GEN_ENABLED cùng cơ chế bỏ qua một lần tắt từ init.
- Áp dụng đúng guard CONFIG_LRU_GEN cho rmap.c từ ESG1 để đường build
  không MGLRU không tham chiếu helper chỉ tồn tại khi bật MGLRU.
- Bổ sung phản hồi I/O wakeup có suy giảm, tối đa năng lực native của cụm CPU.
  I/O boost không được tính thành tải thật để kích OC.
- Giữ lựa chọn tần số từ mô hình EGO; thêm khoảng chờ giảm xung 8 ms như ESG1.
  Giới hạn QoS giảm vẫn có hiệu lực ngay, kể cả trong khoảng chờ này.
- Auto OC bắt đầu đủ điều kiện ở tải 80% năng lực native trên một lõi của cụm,
  duy trì ít nhất 2 ms. Burst tối đa 60 ms, cooldown 180 ms, dừng khi tải dưới 70%.
  Đây là phần trăm trên lõi bận nhất, không phải tổng tải của tám lõi.
- Margin trong burst là 35%; ngoài burst vẫn 12%. Chọn OPP rời rạc từ bảng
  CAL/ASV thực tế, trong giới hạn policy/QoS hiện hành. Dải mong muốn vẫn
  A53 tối đa 2002 MHz và M2 tối đa 2704 MHz, tùy OPP và giới hạn của máy.
- Thêm energy_aware/oc_status: số burst, trần native/model/policy/QoS, xung
  chọn, policy_cur và mức cao nhất driver đã xác nhận với policy trong phiên.
  policy_cur/max_applied là dữ liệu policy; cpuinfo_cur_freq là đường đọc CAL.

## Nháy xanh và PD

Người dùng xác nhận nháy xanh khi tắt màn chỉ xảy ra với boot mới, ESG1 không bị.
Toàn bộ cây nguồn panel và DPU trong hai commit trên có cùng Git tree SHA.
Chưa có log thiết bị để xác định lỗi ở trình tự tắt màn, timeout, hay đường dùng khác.
Việc đưa cấu hình bộ nhớ về ESG1 là thử nghiệm hồi quy; chưa chứng minh sửa lỗi nháy.

Người dùng xác nhận Galaxy A53 nhận PD 15 W với cùng củ/cáp, S8+ thì không;
S8+ nhận PD với sạc dự phòng. Kernel có S2MM005 PD và MAX77865 charger.
Chưa có Source Capabilities/PDO hoặc log attach từ chính củ sạc đang lỗi.
R1 chưa có bản sửa thương lượng PD. Cần log củ sạc và sạc dự phòng để đối chiếu.

## Thử và lấy log

Chỉ flash ALice_boot_R1.img vào phân vùng Boot của đúng máy/ROM.
Giữ boot đang khởi động được và recovery để hoàn nguyên nếu không boot.
Không có yêu cầu flash vendor trong bản này.

Đây là bản kiểm chứng build/offline, chưa chạy trên máy thật. Chưa xác nhận
cải thiện độ mượt, nhiệt, thời lượng pin, OC thực, nháy xanh hay nhận PD trên củ sạc.

Sau khi tái hiện lỗi, lấy snapshot chỉ đọc bằng adb/root shell:

Dùng adb qua Wi-Fi khi cổng USB đang cắm củ sạc. Có thể chạy script trực tiếp
trong terminal root trên điện thoại, rồi lưu đầu ra thành tệp văn bản.

```sh
adb push collect_s8plus_boot_r1.sh /data/local/tmp/
adb shell su -c 'sh /data/local/tmp/collect_s8plus_boot_r1.sh wall' > ALice-wall.txt
adb shell su -c 'sh /data/local/tmp/collect_s8plus_boot_r1.sh powerbank' > ALice-powerbank.txt
adb shell su -c 'sh /data/local/tmp/collect_s8plus_boot_r1.sh screen-off' > ALice-screen-off.txt
```

Lệnh thứ hai chạy khi cắm củ sạc, thứ ba khi cắm sạc dự phòng; lệnh cuối chạy
ngay sau một lần tắt/bật màn có nháy xanh. Có thể lấy log bằng boot hiện tại trước.

Kiểm tra sau khi tải: đặt IMG và SHA256SUMS cùng thư mục rồi chạy
`sha256sum -c SHA256SUMS` (các tệp được liệt kê phải còn cùng nhau).
