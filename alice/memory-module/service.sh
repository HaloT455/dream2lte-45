#!/system/bin/sh
# KernelSU late service: bounded startup, no resident policy loop.
MODDIR=${0%/*}
umask 077
exec > "$MODDIR/status.log" 2>&1
date
uname -r
case "$(uname -r)" in
 *-Alice-V12R69-R8-*|*-Alice-V12R69-R9-*|*-Alice-V12R69-R10-*|*-Alice-V12R69-R11-*|*-Alice-V12R69-R12-*|*-Alice-V12R69-R13-*|*-Alice-V12R69-R14-*|*-Alice-V12R69-R15-*|*-Alice-V12R69-R16-*) ;;
 *) echo ALICE_SUPPORTED_KERNEL_REQUIRED; exit 0;;
esac
tries=0
while [ "$(getprop sys.boot_completed)" != 1 ] && [ "$tries" -lt 60 ]; do
 sleep 2
 tries=$((tries + 1))
done
[ "$(getprop sys.boot_completed)" = 1 ] || { echo ALICE_BOOT_NOT_COMPLETE; exit 0; }
[ -r /proc/pressure/memory ] || { echo ALICE_PSI_UNAVAILABLE; exit 0; }
HELPER=$MODDIR/low-swap.sh
# Reboot discards RAM-only properties; retire any old-boot backup first.
sh "$HELPER" restore || { echo ALICE_BACKUP_REVIEW_REQUIRED; exit 0; }
sh "$HELPER" status
effective=$(getprop sys.lmk.slmk_16up_swap_free_low_percentage)
case "$effective" in
 ''|*[!0-9]*) echo ALICE_NO_EFFECTIVE_SWAP_THRESHOLD; exit 0;;
esac
if [ "$effective" -le 30 ]; then
 echo ALICE_EXISTING_SWAP_THRESHOLD_RETAINED
 exit 0
fi
# The helper requires the exact analyzed LMKD hash, single 3–4 GB zRAM,
# completed boot and adequate available RAM. It verifies or restores writes.
sh "$HELPER" apply
result=$?
sh "$HELPER" status
echo "ALICE_LOW_SWAP_RESULT=$result"
exit 0
