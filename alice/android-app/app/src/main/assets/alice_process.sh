#!/system/bin/sh
# ALICE V12R63 root process helper. Never kill, stop, freeze or change oom_score_adj.
set -f
umask 077
STATE_DIR=/data/adb/alice
STATE_FILE=$STATE_DIR/process-policy.state
case "${1:-}" in
 scan|limit|restore|restore-all|status) OP=$1 ;;
 *) echo ALICE_BAD_COMMAND >&2; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || { echo ALICE_ROOT_REQUIRED >&2; exit 3; }
digits() {
 case "$1" in ''|*[!0-9]*) return 1;; *) return 0;; esac
}
stat_fields() {
 STAT=$(cat "/proc/$1/stat" 2>/dev/null) || return 1
 case "$STAT" in *') '*) REST=${STAT##*) };; *) return 1;; esac
 set -- $REST
 [ "$#" -ge 20 ] || return 1
 START_TICKS=${20}
 NICE_LEVEL=${17}
 CPU_TICKS=$(( ${12} + ${13} ))
 digits "$START_TICKS" && digits "$CPU_TICKS" || return 1
}
proc_info() {
 p=$1
 digits "$p" && [ "$p" -gt 200 ] || return 1
 [ -r "/proc/$p/status" ] && [ -r "/proc/$p/cmdline" ] || return 1
 uid=; rss=0; oom=
 while IFS=':' read -r key value; do
  case "$key" in
   Uid) set -- $value; uid=$1;;
   VmRSS) set -- $value; rss=$1;;
  esac
 done < "/proc/$p/status"
 digits "$uid" && [ "$uid" -ge 10000 ] || return 1
 digits "$rss" || rss=0
 oom=$(cat "/proc/$p/oom_score_adj" 2>/dev/null) || return 1
 name=$(tr '\000' '\n' < "/proc/$p/cmdline" 2>/dev/null | head -n 1 | cut -c 1-96)
 case "$name" in *.*) ;; *) return 1;; esac
 case "$name" in
  com.android.*|com.google.android.*|com.samsung.*|android.*|\
  com.halot455.alice*|com.qualcomm.*|com.sec.*|\
  org.lineageos.*|com.topjohnwu.*|me.weishu.*) return 1;;
  *[!a-zA-Z0-9._:-]*) return 1;;
 esac
 stat_fields "$p" || return 1
 digits "$oom" || return 1
 PROC_START=$START_TICKS
 PROC_NICE=$NICE_LEVEL
 PROC_CPU=$CPU_TICKS
 PROC_UID=$uid
 PROC_RSS=$rss
 PROC_ADJ=$oom
 PROC_NAME=$name
}
ensure_state() {
 [ -d "$STATE_DIR" ] || mkdir -p "$STATE_DIR" || return 1
 chmod 0700 "$STATE_DIR"
 touch "$STATE_FILE" && chmod 0600 "$STATE_FILE"
}
case "$OP" in
scan)
 count=0
 for path in /proc/[0-9]*; do
  pid=${path##*/}
  if proc_info "$pid"; then
   printf '%s|%s|%s|%s|%s|%s|%s|%s\n' \
    "$pid" "$PROC_START" "$PROC_UID" "$PROC_ADJ" \
    "$PROC_NICE" "$PROC_RSS" "$PROC_CPU" "$PROC_NAME"
   count=$(( count + 1 ))
   [ "$count" -lt 220 ] || break
  fi
 done
 ;;
limit)
 pid=${2:-}; start=${3:-}
 digits "$pid" && digits "$start" || exit 2
 proc_info "$pid" || { echo ALICE_PROCESS_NOT_ELIGIBLE; exit 4; }
 [ "$PROC_START" = "$start" ] || { echo ALICE_PID_REUSED; exit 5; }
 [ "$PROC_ADJ" -ge 900 ] || { echo ALICE_FOREGROUND_OR_SERVICE_PROTECTED; exit 6; }
 [ "$PROC_NICE" -lt 10 ] || { echo ALICE_ALREADY_LIMITED; exit 0; }
 ensure_state || exit 7
 grep -q "^$pid $start " "$STATE_FILE" 2>/dev/null || \
  printf '%s %s %s\n' "$pid" "$start" "$PROC_NICE" >> "$STATE_FILE"
 renice 10 -p "$pid" >/dev/null 2>&1 || { echo ALICE_RENICE_FAILED; exit 8; }
 echo "ALICE_LIMITED $pid ${PROC_NAME} nice=10"
 ;;
restore)
 pid=${2:-}; start=${3:-}
 digits "$pid" && digits "$start" || exit 2
 [ -f "$STATE_FILE" ] || { echo ALICE_NOTHING_TO_RESTORE; exit 0; }
 original=$(awk -v p="$pid" -v s="$start" '$1==p && $2==s {print $3;exit}' "$STATE_FILE")
 case "$original" in ''|*[!0-9-]*) echo ALICE_NOT_TRACKED; exit 3;; esac
 if stat_fields "$pid" && [ "$START_TICKS" = "$start" ]; then
  renice "$original" -p "$pid" >/dev/null 2>&1 || exit 8
 fi
 tmp="$STATE_FILE.$$"
 awk -v p="$pid" -v s="$start" '!($1==p && $2==s)' "$STATE_FILE" > "$tmp"
 mv -f "$tmp" "$STATE_FILE"
 echo "ALICE_RESTORED $pid"
 ;;
restore-all)
 [ -f "$STATE_FILE" ] || exit 0
 cp "$STATE_FILE" "$STATE_FILE.work.$$" || exit 8
 while read -r pid start original; do
  digits "$pid" && digits "$start" || continue
  case "$original" in ''|*[!0-9-]*) continue;; esac
  if stat_fields "$pid" && [ "$START_TICKS" = "$start" ]; then
   renice "$original" -p "$pid" >/dev/null 2>&1 || :
  fi
 done < "$STATE_FILE.work.$$"
 rm -f "$STATE_FILE.work.$$"
 : > "$STATE_FILE"
 echo ALICE_ALL_RESTORED
 ;;
status)
 [ -f "$STATE_FILE" ] && cat "$STATE_FILE" || echo ALICE_NO_PROCESS_ADJUSTMENTS
 ;;
esac
