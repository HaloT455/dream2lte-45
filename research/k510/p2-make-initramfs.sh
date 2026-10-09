#!/usr/bin/env bash
# P2A: build minimal ARM64 debug /init and reproducible initramfs.
# Designed for compiler checks and later controlled early-boot research.
set -euo pipefail
OUT="$(readlink -m "$1")"
mkdir -p "$OUT"
cat > "$OUT/init.c" <<'C'
// SPDX-License-Identifier: GPL-2.0-only
// Alice K510 P2A: static ARM64 PID1, minimal persistent diagnostics.
// No Android vendor or GPU/modem bring-up is attempted here.
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <unistd.h>

static void log_line(const char *msg)
{
    int fd = open("/dev/kmsg", O_WRONLY | O_CLOEXEC);
    if (fd >= 0) {
        write(fd, msg, strlen(msg));
        close(fd);
    }
    fd = open("/dev/console", O_WRONLY | O_CLOEXEC);
    if (fd >= 0) {
        write(fd, msg, strlen(msg));
        close(fd);
    }
}

int main(void)
{
    mount("devtmpfs", "/dev", "devtmpfs", MS_NOSUID, "mode=0755");
    mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL);
    mount("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL);
    log_line("<6>ALICE_K510_P2A_INIT_REACHED Linux 5.10\n");
    for (;;) {
        log_line("<6>ALICE_K510_P2A_HEARTBEAT\n");
        sleep(20);
    }
    return 0;
}
C
aarch64-linux-gnu-gcc -Os -static -s -Wall -Wextra -o "$OUT/init" "$OUT/init.c"
aarch64-linux-gnu-readelf -h "$OUT/init" | grep -q 'Machine:.*AArch64'

# Produce unprivileged "newc" cpio with device nodes, without root or mknod.
python3 - "$OUT/init" "$OUT/initramfs.cpio" <<'PY'
from pathlib import Path
import os,stat,sys,time
binary=Path(sys.argv[1]).read_bytes()
target=Path(sys.argv[2])
parts=[]
counter=0
def add(name,mode,data=b'',major=0,minor=0):
    global counter
    counter+=1
    name_bytes=name.encode()+b'\0'
    fields=[counter,mode,0,0,1,0,len(data),0,0,major,minor,len(name_bytes),0]
    header=b'070701'+b''.join(('%08x'%x).encode() for x in fields)
    assert len(header)==110
    record=header+name_bytes
    record+=b'\0'*((-len(record))%4)
    record+=data
    record+=b'\0'*((-len(data))%4)
    parts.append(record)
for d in ('.','dev','proc','sys','tmp'):
    add(d,stat.S_IFDIR|0o755)
add('dev/console',stat.S_IFCHR|0o600,b'',5,1)
add('dev/null',stat.S_IFCHR|0o666,b'',1,3)
add('init',stat.S_IFREG|0o755,binary)
add('TRAILER!!!',0)
target.write_bytes(b''.join(parts))
print('newc bytes:',target.stat().st_size)
PY
gzip -n -9 -c "$OUT/initramfs.cpio" > "$OUT/initramfs.cpio.gz"
echo "P2A static aarch64 /init + initramfs: $OUT"
echo 'P2A compiler artifact; no boot image generated.'
