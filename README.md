# ALice S8+ Exynos8895 — One UI 8 / Android 16

Nguồn kernel hợp nhất: [alice-unified](https://github.com/HaloT455/dream2lte-45/tree/alice-unified), commit [6b75fa25](https://github.com/HaloT455/dream2lte-45/commit/6b75fa2592ff7d98fd4dc929c09d1b6072a9ec25).

Nguồn vendor nền new.dat: [Vendor-45- / work/s8plus-newdat-unified-20261126](https://github.com/HaloT455/Vendor-45-/tree/work/s8plus-newdat-unified-20261126), commit [23f89db6](https://github.com/HaloT455/Vendor-45-/commit/23f89db645143d37a644deb237f8670136ad141d).

- [CI kernel và boot thật](https://github.com/HaloT455/dream2lte-45/actions/runs/45851295261): tạo ALice_boot.img bằng kernel vừa biên dịch, giữ ramdisk EGO gốc đã xác minh SHA-256.
- [CI vendor thật](https://github.com/HaloT455/Vendor-45-/actions/runs/45852326144): tạo ALice_vendor.img từ nền vendor.new.dat.br, tái tạo và kiểm metadata của 1.382 mục.

Giữ Energy Aware EGO, dải energy state A53 455–2002 MHz / M2 741–2704 MHz, KernelSU AutoHook, LZ4KD, PSI, driver LED và camera. Tắt kernel LMK để dùng LMKD của ROM; hoạt động thực tế của LMKD cần kiểm tra trên máy. Radio nền new.dat giữ nguyên; Dual SIM tạm hoãn.

Main là trang dẫn tới các nhánh nguồn đang build. Các artifact có SHA256SUMS và provenance. CI thành công xác nhận build/kiểm tra offline, chưa xác nhận khởi động, camera hoặc LED trên thiết bị thật.
