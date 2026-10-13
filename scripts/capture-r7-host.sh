#!/usr/bin/env bash
# Run on Linux with the phone connected by adb. No settings are changed.
set -euo pipefail
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for command_name in adb timeout; do
    command -v "$command_name" >/dev/null || { echo "Missing: $command_name" >&2; exit 1; }
done
adb get-state >/dev/null
out_dir=${1:-"ALICE_UI_$(date +%Y%m%d_%H%M%S)"}
mkdir -p -- "$out_dir"
adb push "$script_dir/capture-r7-device.sh" /data/local/tmp/alice-r7-capture.sh >/dev/null
timeout 8s adb shell 'su -c "id; uname -r; cat /sys/kernel/mm/lru_gen/enabled"' > "$out_dir/identity.log" 2>&1
if ! rg_check=$(cat "$out_dir/identity.log") || [[ "$rg_check" != *"uid=0"* ]]; then
    echo "Root capture unavailable; see $out_dir/identity.log" >&2
    exit 1
fi
children=()
stop_children() {
    for child in "${children[@]}"; do kill "$child" 2>/dev/null || true; done
    for child in "${children[@]}"; do wait "$child" 2>/dev/null || true; done
}
trap stop_children EXIT INT TERM
timeout 65s adb logcat -b system -b events -b crash -v threadtime -T 1 > "$out_dir/android.log" 2>&1 &
children+=("$!")
timeout 65s adb exec-out 'su -c "dmesg -w"' > "$out_dir/kernel.log" 2>&1 &
children+=("$!")
echo "Mở app 1 rồi app 2, về Home/kéo thông báo như lúc bị lag. Log đang lưu trên laptop."
echo "Nếu máy treo, log đã nhận vẫn còn trong: $out_dir"
timeout 65s adb exec-out 'su -c "sh /data/local/tmp/alice-r7-capture.sh"' > "$out_dir/samples.log" 2>&1 || true
stop_children
trap - EXIT INT TERM
echo "Đã lưu: $out_dir"
