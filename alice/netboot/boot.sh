#!/system/bin/sh
# ALICE_NETBOOT_R1: finite startup task embedded in the kernel's init RC hook.
STATE=${ALICE_NET_STATE:-/data/adb/alice-netboot}
umask 077
mkdir -p "$STATE" || exit 1
chmod 0700 "$STATE" || exit 1
exec >> "$STATE/status.log" 2>&1
echo ALICE_NETBOOT_R1_START
case "$1" in restore|status) ;; *)
 [ ! -e "$STATE/disable" ] || { echo ALICE_NETBOOT_DISABLED; exit 0; };; esac
HOST=dns.adguard-dns.com

read_dns() {
 MODE=$(settings get global private_dns_mode 2>/dev/null) || return 1
 SPEC=$(settings get global private_dns_specifier 2>/dev/null) || return 1
 case "$MODE" in null|off|opportunistic|hostname) ;; *) return 1;; esac
 case "$SPEC" in *[!A-Za-z0-9._-]*) return 1;; esac
}
write_dns() {
 if [ "$2" = null ]; then settings delete global "$1" >/dev/null 2>&1
 else settings put global "$1" "$2" >/dev/null 2>&1; fi
}
restore_dns_pair() {
 write_dns private_dns_specifier "$2" && write_dns private_dns_mode "$1" || return 1
 read_dns && [ "$MODE" = "$1" ] && [ "$SPEC" = "$2" ]
}
apply_dns() {
 read_dns || return 1
 [ "$MODE" != hostname ] || [ "$SPEC" != "$HOST" ] || { echo DNS_ALREADY_SET; return 0; }
 OLD_MODE=$MODE; OLD_SPEC=$SPEC
 if [ ! -d "$STATE/dns-state" ]; then
  TMP=$STATE/dns-state.tmp.$$
  mkdir "$TMP" || return 1
  printf '%s\n' "$OLD_MODE" > "$TMP/mode" &&
   printf '%s\n' "$OLD_SPEC" > "$TMP/specifier" &&
   mv "$TMP" "$STATE/dns-state" || { rm -rf "$TMP"; return 1; }
 fi
 if write_dns private_dns_specifier "$HOST" && write_dns private_dns_mode hostname &&
    read_dns && [ "$MODE" = hostname ] && [ "$SPEC" = "$HOST" ]; then
  echo DNS_SETTINGS_APPLIED_NETWORK_VALIDATION_UNCHECKED
  return 0
 fi
 restore_dns_pair "$OLD_MODE" "$OLD_SPEC" && echo DNS_WRITE_ROLLED_BACK || echo DNS_ROLLBACK_FAILED
 return 1
}

wifi_supported() {
 WIFI_HELP=$(cmd wifi help 2>&1) || return 1
 printf '%s\n' "$WIFI_HELP" | grep -q 'set-network-selection-config' || return 2
 printf '%s\n' "$WIFI_HELP" | grep -q 'associated_network_selection_override' || return 2
}
apply_wifi() {
 wifi_supported
 support=$?
 [ "$support" != 2 ] || { echo WIFI_SELECTION_API_UNSUPPORTED; return 0; }
 [ "$support" = 0 ] || return 1
 # AOSP: disable selection of a different network WHILE ASSOCIATED only.
 # Disconnected autojoin, saved profiles, selected SSID and BSSID are untouched.
 # Keep sufficiency checks enabled; do not request aggressive scans or RF power.
 if cmd wifi set-network-selection-config enabled enabled -a 2; then
  echo WIFI_STAY_CONNECTED_REQUESTED_AUTOJOIN_UNCHANGED
  return 0
 fi
 echo WIFI_SELECTION_REQUEST_FAILED
 return 1
}

restore_all() {
 touch "$STATE/disable" || return 1
 if [ -r "$STATE/dns-state/mode" ] && [ -r "$STATE/dns-state/specifier" ] && read_dns; then
  if [ "$MODE" = hostname ] && [ "$SPEC" = "$HOST" ]; then
   restore_dns_pair "$(cat "$STATE/dns-state/mode")" "$(cat "$STATE/dns-state/specifier")" || return 1
   echo DNS_PREVIOUS_SETTINGS_RESTORED
  else echo DNS_USER_CHANGE_PRESERVED; fi
 fi
 if wifi_supported; then
  # Restore the platform default override, not an unknown prior custom policy.
  cmd wifi set-network-selection-config enabled enabled -a 0 || return 1
  echo WIFI_PLATFORM_DEFAULT_REQUESTED
 fi
}

case "$1" in
 restore) restore_all; exit $?;;
 status) read_dns && printf 'mode=%s\nhost=%s\n' "$MODE" "$SPEC"; exit $?;;
 ''|apply) ;;
 *) echo ALICE_NETBOOT_INVALID_ACTION; exit 2;;
esac
DNS_DONE=0; WIFI_DONE=0; tries=0
while [ "$tries" -lt 30 ]; do
 [ ! -e "$STATE/disable" ] || { echo ALICE_NETBOOT_DISABLED; exit 0; }
 [ "$DNS_DONE" = 1 ] || { apply_dns && DNS_DONE=1; }
 [ "$WIFI_DONE" = 1 ] || { apply_wifi && WIFI_DONE=1; }
 [ "$DNS_DONE$WIFI_DONE" != 11 ] || break
 tries=$((tries + 1))
 [ "$tries" -lt 30 ] && sleep 2
done
echo "ALICE_NETBOOT_R1_END dns=$DNS_DONE wifi=$WIFI_DONE tries=$tries"
exit 0
