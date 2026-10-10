#!/usr/bin/env bash
# P11: build isolated AArch64 PID1 diagnostic with read-only hardware enumeration.
# Designed for compiler checks and later controlled early-boot research.
set -euo pipefail
OUT="$(readlink -m "$1")"
mkdir -p "$OUT"
cat > "$OUT/init.c" <<'C'
// SPDX-License-Identifier: GPL-2.0-only
// ALICE_K510_P11: read-only first-userspace boot evidence and hardware inventory.
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/types.h>
#include <unistd.h>

static void log_line(const char *msg)
{
    /* /dev/kmsg may be persisted to ramoops; /dev/console is a fallback. */
    int fd = open("/dev/kmsg", O_WRONLY | O_CLOEXEC);
    if (fd >= 0) {
        (void)write(fd, msg, strlen(msg));
        close(fd);
    }
    fd = open("/dev/console", O_WRONLY | O_CLOEXEC);
    if (fd >= 0) {
        (void)write(fd, msg, strlen(msg));
        close(fd);
    }
}
static void log_kv(const char *tag, const char *value)
{
    char line[320];
    snprintf(line, sizeof(line), "<6>ALICE_K510_P11_%s=%s\n", tag, value);
    log_line(line);
}
static void log_read(const char *tag, const char *path)
{
    char buf[256] = {0};
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        log_kv(tag, "UNAVAILABLE");
        return;
    }
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n <= 0) {
        log_kv(tag, "EMPTY_OR_READ_FAILED");
        return;
    }
    for (ssize_t i = 0; i < n; i++) {
        if (buf[i] == '\n' || buf[i] == '\r' || buf[i] == '\t')
            buf[i] = ' ';
    }
    buf[n] = '\0';
    log_kv(tag, buf);
}
static void log_dir(const char *tag, const char *path)
{
    /* Cap output at 16 entries to avoid overrunning the tiny 16 KiB pstore. */
    DIR *dir = opendir(path);
    if (!dir) {
        log_kv(tag, "UNAVAILABLE");
        return;
    }
    char result[256] = {0};
    size_t used = 0;
    unsigned n = 0;
    struct dirent *de;
    while ((de = readdir(dir)) != NULL && n < 16) {
        if (de->d_name[0] == '.')
            continue;
        size_t length = strlen(de->d_name);
        if (length + used + 2 >= sizeof(result))
            break;
        if (used)
            result[used++] = ',';
        memcpy(result + used, de->d_name, length);
        used += length;
        result[used] = 0;
        n++;
    }
    closedir(dir);
    log_kv(tag, n ? result : "NONE");
}
int main(void)
{
    char line[150];
    int rc_dev = mount("devtmpfs", "/dev", "devtmpfs", MS_NOSUID, "mode=0755");
    int rc_proc = mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL);
    int rc_sys = mount("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL);
    /* Distinct P11 marker: P10 did not contain this string. */
    log_line("<6>ALICE_K510_P11_PID1_REACHED_LINUX_5_10_262\n");
    snprintf(line, sizeof(line), "<6>ALICE_K510_P11_PID=%ld MOUNTS=%d,%d,%d\n",
             (long)getpid(), rc_dev, rc_proc, rc_sys);
    log_line(line);
    log_read("UPTIME_FIRST", "/proc/uptime");
    log_read("KERNEL_RELEASE", "/proc/sys/kernel/osrelease");
    log_dir("POWER_SUPPLIES", "/sys/class/power_supply");
    log_dir("SCSI_HOSTS", "/sys/class/scsi_host");
    log_dir("BLOCK_DEVICES", "/sys/block");
    log_dir("PLATFORM_DEVICES", "/sys/bus/platform/devices");
    /* No read or write to /dev/block/; no battery regulator changes. */
    for (unsigned tick = 0;; ++tick) {
        snprintf(line, sizeof(line), "<6>ALICE_K510_P11_HEARTBEAT_%u\n", tick);
        log_line(line);
        if ((tick % 3u) == 0u)
            log_read("UPTIME", "/proc/uptime");
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
echo "P11 static aarch64 /init + read-only inventory + initramfs: $OUT"
echo 'P11 compiler artifact; no boot image generated here.'
