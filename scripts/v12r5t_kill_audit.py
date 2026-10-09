#!/usr/bin/env python3
"""Read-only Samsung LMKD/Chimera victim audit from adb logcat output.

Example:
  adb logcat -d -v time -s lmkd:I ActivityManager:I Chimera:V |
    python3 scripts/v12r5t_kill_audit.py

This tool does NOT change oom_score_adj, kill policy, app standby buckets
or process lifetime. Foreground/audio/call state cannot be inferred from
package names alone.
"""
import collections
import re
import sys

LMKD = re.compile(r"lmkd.*?Reclaim '([^']+)' .*?oom_score_adj\s+(\d+).*?reason:\s*(.*)", re.I)
AM = re.compile(r"ActivityManager.*?Killing\s+\d+:([^\s(]+).*?\(adj\s+(\d+)\):\s*(.*)", re.I)
CRITICAL = {
    "system_server", "surfaceflinger", "com.android.systemui",
    "com.android.phone", "com.android.bluetooth", "audioserver",
    "com.android.ims", "com.samsung.ims", "com.sec.imsservice",
}
# Context-sensitive UI/process names are deliberately NOT immortal.
CONTEXT = (
    "incallui", "telephonyui", "inputmethod", "music", "camera",
    "navigation", "bluetooth",
)

def classify(package, adj):
    # adj is a snapshot at kill time; real foreground/service state matters.
    if package in CRITICAL:
        return "critical-name (investigate adj/state)"
    if any(s in package.lower() for s in CONTEXT):
        return "context-sensitive (verify call/media/input state)"
    if adj >= 900:
        return "cached candidate"
    if adj >= 800:
        return "background candidate"
    return "elevated priority (investigate)"

def main():
    events = []
    for line in sys.stdin:
        match = LMKD.search(line)
        actor = "lmkd"
        if not match:
            match = AM.search(line)
            actor = "ActivityManager/Chimera"
        if not match:
            continue
        package, adj, reason = match.groups()
        events.append((actor, package, int(adj), reason.strip(), classify(package, int(adj))))
    print(f"Kill/reclaim log entries: {len(events)}")
    for actor, count in collections.Counter(x[0] for x in events).most_common():
        print(f"  {actor}: {count}")
    for kind, count in collections.Counter(x[4] for x in events).most_common():
        print(f"  {kind}: {count}")
    important = [x for x in events if not x[4].endswith("candidate")]
    print(f"\nImportant/context candidates ({len(important)}):")
    for actor, package, adj, reason, kind in important[-35:]:
        print(f"  [{actor}] {package} adj={adj}: {kind}; {reason[:120]}")
    print("\nNote: activity state is NOT proven by a log's package name or adj alone.")
    print("Do not whitelist all system packages or prevent emergency OOM kills.")

if __name__ == "__main__":
    main()
