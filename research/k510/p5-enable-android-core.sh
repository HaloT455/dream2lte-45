#!/usr/bin/env bash
# P5 Android kernel-core migration from V12R5T semantic requirements.
# 5.10 native implementations ONLY (no blindly copied 4.4 vendor drivers).
set -euo pipefail
TREE="$1"
OUT="$2"
test -f "$OUT/.config"
test -f "$TREE/scripts/config"
cfg="$TREE/scripts/config"
"$cfg" --file "$OUT/.config" \
  --enable ANDROID \
  --enable ANDROID_BINDER_IPC \
  --enable ANDROID_BINDERFS \
  --set-str ANDROID_BINDER_DEVICES 'binder,hwbinder,vndbinder' \
  --enable CGROUPS \
  --enable NAMESPACES \
  --enable SECURITY \
  --enable SECURITYFS \
  --enable SECURITY_SELINUX \
  --enable FS_ENCRYPTION \
  --enable EROFS_FS \
  --enable EROFS_FS_XATTR \
  --enable EROFS_FS_SECURITY \
  --enable EROFS_FS_ZIP \
  --enable F2FS_FS \
  --enable F2FS_FS_XATTR \
  --enable F2FS_FS_SECURITY \
  --enable F2FS_FS_ENCRYPTION \
  --enable BLK_DEV_DM \
  --enable DM_CRYPT \
  --enable DM_VERITY \
  --enable CONFIGFS_FS \
  --enable USB_SUPPORT \
  --enable USB \
  --enable USB_GADGET \
  --enable USB_LIBCOMPOSITE \
  --enable USB_CONFIGFS \
  --enable USB_CONFIGFS_F_FS
make -s -C "$TREE" O="$OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
# Hard gating: these must exist as built-in because the current firmware
# uses binder / EROFS / F2FS. This is NOT Android/vendor compatibility proof.
for key in ANDROID_BINDER_IPC EROFS_FS F2FS_FS SECURITY_SELINUX BLK_DEV_DM DM_CRYPT DM_VERITY CGROUPS NAMESPACES; do
  if ! grep -qx "CONFIG_$key=y" "$OUT/.config"; then
    echo "P5 FAIL: missing native Linux 5.10 built-in CONFIG_$key=y" >&2
    exit 21
  fi
done
grep -qx 'CONFIG_ANDROID_BINDER_DEVICES="binder,hwbinder,vndbinder"' "$OUT/.config" || {
    echo 'P5 FAIL: binder device names not retained' >&2
    exit 22
}
echo 'P5 built-in Android/kernel filesystem/security feature gate: PASS'
# Optional config dependencies are not silently claimed; report exact result.
for key in ANDROID_BINDERFS EROFS_FS_ZIP EROFS_FS_SECURITY F2FS_FS_ENCRYPTION USB_CONFIGFS USB_CONFIGFS_F_FS; do
  grep -E "^CONFIG_$key=|^# CONFIG_$key is not set" "$OUT/.config" || echo "CONFIG_$key: unrecognized / no selectable dependency"
done
echo "WARNING: This stage does not port PMIC, GPU, camera or vendor UFS PHY."
