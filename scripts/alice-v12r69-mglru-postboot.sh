#!/system/bin/sh
# R5 retires automatic post-boot enable. Keep the entry read-only if installed.
SYS=/sys/kernel/mm/lru_gen/enabled
printf 'ALICE R5: manual LRU only; current=%s\n' "$(cat "$SYS" 2>/dev/null || echo unavailable)"
