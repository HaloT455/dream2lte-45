#!/system/bin/sh
# ALICE V12R69: optional one-shot post-boot MGLRU restoration.
# Install explicitly as /data/adb/service.d/99-alice-mglru-restore.sh (0755).
# Intended for One UI port's init.mglru.sh disabling MGLRU on a nominal 4 GiB device.
# No persistent loop; never modifies LMKD, thermal, governor or swap.
LOG=/data/local/tmp/alice-mglru-postboot.log
SYS=/sys/kernel/mm/lru_gen/enabled
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
[ -r "$SYS" ] && [ -w "$SYS" ] || exit 0
n=0
while [ "$(getprop sys.boot_completed)" != "1" ] && [ "$n" -lt 120 ]; do
  sleep 2
  n=$((n+1))
done
[ "$(getprop sys.boot_completed)" = "1" ] || { log "boot not completed"; exit 0; }
# Let init actions finish, then apply once. Do NOT forcibly re-enable if toggled later.
sleep 15
case "$(cat "$SYS" 2>/dev/null)" in
  1) log "MGLRU already enabled"; exit 0 ;;
  0)
    # Verify known OneUI policy script; otherwise abstain.
    [ -f /system/bin/init.mglru.sh ] || { log "unknown ROM disable source; no change"; exit 0; }
    if grep -q 'lru_gen/enabled' /system/bin/init.mglru.sh 2>/dev/null; then
      # Do not race a late ROM write or override a manual OFF after boot.
      [ "$(cat "$SYS" 2>/dev/null)" = "0" ] || exit 0
      echo 1 > "$SYS" 2>/dev/null || { log "enable failed"; exit 1; }
      log "one-shot restore result=$(cat "$SYS" 2>/dev/null)"
    else
      log "policy script did not reference MGLRU; no change"
    fi
    ;;
  *) log "unexpected MGLRU state; no change" ;;
esac
