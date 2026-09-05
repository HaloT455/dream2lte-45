package com.alice.kerneltrace;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.SystemClock;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.TimeUnit;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

final class TraceUtils {
    static final String PREFS = "trace_state";
    static final String KEY_ACTIVE = "active";
    static final String KEY_START_ELAPSED = "start_elapsed";
    static final String KEY_SESSION = "session_path";
    static final String KEY_LATEST_ZIP = "latest_zip";
    static final int MAX_COMMAND_BYTES = 8 * 1024 * 1024;

    private TraceUtils() {}

    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static File baseDir(Context context) {
        File external = context.getExternalFilesDir(null);
        File base = new File(external != null ? external : context.getFilesDir(),
                "ALiceKernelTrace");
        if (!base.exists() && !base.mkdirs()) {
            throw new IllegalStateException("Cannot create " + base);
        }
        return base;
    }

    static File newSessionDir(Context context) {
        SimpleDateFormat format = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US);
        format.setTimeZone(TimeZone.getDefault());
        File session = new File(baseDir(context), "session-" + format.format(new Date()));
        if (!session.mkdirs()) {
            throw new IllegalStateException("Cannot create " + session);
        }
        return session;
    }

    static void writeText(File file, String text) throws IOException {
        File parent = file.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IOException("Cannot create " + parent);
        }
        try (FileOutputStream output = new FileOutputStream(file, false)) {
            output.write(text.getBytes(StandardCharsets.UTF_8));
            output.flush();
            output.getFD().sync();
        }
    }

    static synchronized void appendEvent(File session, String event) {
        if (session == null) return;
        File file = new File(session, "events.txt");
        String line = System.currentTimeMillis() + " elapsed=" + SystemClock.elapsedRealtime()
                + " " + event + "\n";
        try (FileOutputStream output = new FileOutputStream(file, true)) {
            output.write(line.getBytes(StandardCharsets.UTF_8));
            output.flush();
            output.getFD().sync();
        } catch (IOException ignored) {
        }
    }

    static String shellQuote(String value) {
        return "'" + value.replace("'", "'\\''") + "'";
    }

    static CommandResult runSu(String command, long timeoutSeconds) {
        return runCommand(Arrays.asList("su", "-c", command), timeoutSeconds);
    }

    static CommandResult runCommand(List<String> command, long timeoutSeconds) {
        Process process = null;
        ByteArrayOutputStream captured = new ByteArrayOutputStream();
        Thread reader = null;
        try {
            ProcessBuilder builder = new ProcessBuilder(command);
            builder.redirectErrorStream(true);
            process = builder.start();
            Process finalProcess = process;
            reader = new Thread(() -> copyLimited(finalProcess.getInputStream(), captured),
                    "alice-command-reader");
            reader.start();
            boolean finished = process.waitFor(timeoutSeconds, TimeUnit.SECONDS);
            if (!finished) {
                process.destroy();
                if (!process.waitFor(2, TimeUnit.SECONDS)) process.destroyForcibly();
            }
            if (reader != null) reader.join(2000);
            return new CommandResult(finished ? process.exitValue() : 124,
                    captured.toString(StandardCharsets.UTF_8.name()));
        } catch (Exception error) {
            if (process != null) process.destroyForcibly();
            return new CommandResult(127, error.toString());
        }
    }

    private static void copyLimited(InputStream input, ByteArrayOutputStream output) {
        byte[] buffer = new byte[8192];
        int total = 0;
        try {
            int count;
            while ((count = input.read(buffer)) != -1) {
                int writable = Math.min(count, Math.max(0, MAX_COMMAND_BYTES - total));
                if (writable > 0) output.write(buffer, 0, writable);
                total += count;
            }
        } catch (IOException ignored) {
        }
    }

    static boolean rootAvailable() {
        CommandResult result = runSu("id", 8);
        return result.code == 0 && result.output.contains("uid=0");
    }

    static String basicStatus() {
        String command = "echo '[id]'; id; "
                + "echo '[uname]'; uname -a; "
                + "echo '[selinux]'; getenforce 2>/dev/null || true; "
                + "echo '[mglru]'; "
                + "for f in /sys/kernel/mm/lru_gen/enabled /sys/kernel/lru_gen/enabled "
                + "/sys/module/lru_gen/parameters/enabled; do "
                + "[ -r \"$f\" ] && echo \"$f=$(cat \"$f\")\"; done; "
                + "echo '[governors]'; "
                + "for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_governor; do "
                + "[ -r \"$f\" ] && echo \"$f=$(cat \"$f\")\"; done; "
                + "echo '[radio]'; getprop gsm.sim.state; getprop gsm.network.type; "
                + "getprop persist.radio.multisim.config";
        CommandResult result = runSu(command, 15);
        return result.output.trim();
    }

    static void collectSnapshot(File output, String phase) {
        String command = "echo 'ALice Kernel Trace snapshot: " + phase + "'; "
                + "date; echo '[identity]'; id; uname -a; cat /proc/cmdline; "
                + "echo '[selinux]'; getenforce 2>/dev/null || true; "
                + "echo '[kernel-config]'; zcat /proc/config.gz 2>/dev/null | "
                + "grep -E 'LRU_GEN|SIMPLE_LMK|LOW_MEMORY|SCHEDUTIL|SCHED_WALT|KSU|EROFS|F2FS' || true; "
                + "echo '[mglru-nodes]'; for f in /sys/kernel/mm/lru_gen/* "
                + "/sys/kernel/lru_gen/* /sys/module/lru_gen/parameters/*; do "
                + "[ -r \"$f\" ] && echo \"--- $f\" && cat \"$f\"; done; "
                + "echo '[memory]'; cat /proc/meminfo; cat /proc/vmstat; "
                + "for f in /proc/pressure/memory /sys/block/zram0/mm_stat "
                + "/sys/block/zram0/comp_algorithm; do [ -r \"$f\" ] && "
                + "echo \"--- $f\" && cat \"$f\"; done; "
                + "echo '[cpu]'; for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_*; do "
                + "[ -r \"$f\" ] && echo \"$f=$(cat \"$f\")\"; done; "
                + "echo '[thermal]'; for z in /sys/class/thermal/thermal_zone*; do "
                + "[ -r \"$z/type\" ] && echo \"$(cat \"$z/type\")=$(cat \"$z/temp\" 2>/dev/null)\"; done; "
                + "echo '[network]'; ip -details addr 2>/dev/null || ifconfig -a 2>/dev/null; "
                + "echo '[radio-properties]'; getprop | grep -Ei 'radio|ril|ims|volte|vowifi|epdg|carrier|multisim' || true; "
                + "echo '[phone-services]'; service list | grep -Ei 'phone|ims|isub|telephony' || true; "
                + "echo '[subscriptions]'; dumpsys isub 2>/dev/null || true; "
                + "echo '[telephony]'; dumpsys telephony.registry 2>/dev/null || true";
        CommandResult result = runSu(command, 30);
        try {
            writeText(output, result.output + "\nexit_code=" + result.code + "\n");
        } catch (IOException ignored) {
        }
    }

    static synchronized List<File> recoverInterrupted(Context context, boolean force) {
        List<File> recovered = new ArrayList<>();
        File base;
        try {
            base = baseDir(context);
        } catch (RuntimeException error) {
            return recovered;
        }
        SharedPreferences preferences = prefs(context);
        String activePath = preferences.getString(KEY_SESSION, "");
        File[] sessions = base.listFiles(File::isDirectory);
        if (sessions == null) return recovered;
        Arrays.sort(sessions, Comparator.comparing(File::getName));
        for (File session : sessions) {
            File running = new File(session, "RUNNING");
            if (!running.exists()) continue;
            if (!force && preferences.getBoolean(KEY_ACTIVE, false)
                    && session.getAbsolutePath().equals(activePath)) continue;
            appendEvent(session, "RECOVERY_STARTED");
            collectRecovery(session);
            if (!running.delete()) {
                try { writeText(running, "recovered\n"); } catch (IOException ignored) {}
            }
            try {
                writeText(new File(session, "INTERRUPTED.txt"),
                        "The previous recording did not finish normally.\n"
                                + "Recovered at epoch_ms=" + System.currentTimeMillis() + "\n");
                File zip = new File(base, session.getName() + "-recovered.zip");
                zipDirectory(session, zip);
                recovered.add(zip);
                preferences.edit().putString(KEY_LATEST_ZIP, zip.getAbsolutePath()).apply();
            } catch (IOException ignored) {
            }
        }
        if (force && !recovered.isEmpty()) {
            preferences.edit().putBoolean(KEY_ACTIVE, false).remove(KEY_SESSION).apply();
        }
        return recovered;
    }

    private static void collectRecovery(File session) {
        String command = "echo 'ALice post-reboot recovery'; date; uname -a; "
                + "echo '[pstore and last_kmsg]'; "
                + "for f in /sys/fs/pstore/* /proc/last_kmsg; do "
                + "if [ -r \"$f\" ]; then echo \"===== $f =====\"; cat \"$f\"; fi; done; "
                + "echo '[current dmesg]'; dmesg; "
                + "echo '[current logcat tail]'; logcat -b all -d -v threadtime -t 5000 2>/dev/null";
        CommandResult result = runSu(command, 30);
        try {
            writeText(new File(session, "post-reboot-recovery.txt"),
                    result.output + "\nexit_code=" + result.code + "\n");
        } catch (IOException ignored) {
        }
    }

    static synchronized void zipDirectory(File directory, File output) throws IOException {
        File temporary = new File(output.getParentFile(), output.getName() + ".part");
        if (temporary.exists() && !temporary.delete()) {
            throw new IOException("Cannot replace " + temporary);
        }
        try (ZipOutputStream zip = new ZipOutputStream(new BufferedOutputStream(
                new FileOutputStream(temporary)))) {
            addToZip(directory, directory, zip);
        }
        if (output.exists() && !output.delete()) throw new IOException("Cannot replace zip");
        if (!temporary.renameTo(output)) throw new IOException("Cannot finalize zip");
    }

    private static void addToZip(File root, File file, ZipOutputStream zip) throws IOException {
        File[] children = file.listFiles();
        if (children == null) return;
        Arrays.sort(children, Comparator.comparing(File::getName));
        byte[] buffer = new byte[64 * 1024];
        for (File child : children) {
            String relative = root.toURI().relativize(child.toURI()).getPath();
            if (child.isDirectory()) {
                addToZip(root, child, zip);
                continue;
            }
            ZipEntry entry = new ZipEntry(relative);
            entry.setTime(child.lastModified());
            zip.putNextEntry(entry);
            try (BufferedInputStream input = new BufferedInputStream(new FileInputStream(child))) {
                int count;
                while ((count = input.read(buffer)) != -1) zip.write(buffer, 0, count);
            }
            zip.closeEntry();
        }
    }

    static File latestZip(Context context) {
        String saved = prefs(context).getString(KEY_LATEST_ZIP, "");
        if (!saved.isEmpty()) {
            File file = new File(saved);
            if (file.isFile()) return file;
        }
        File[] files = baseDir(context).listFiles((dir, name) -> name.endsWith(".zip"));
        if (files == null || files.length == 0) return null;
        return Arrays.stream(files).max(Comparator.comparingLong(File::lastModified)).orElse(null);
    }

    static String deviceMetadata() {
        return "app=ALice Kernel Trace 2.0\n"
                + "epoch_ms=" + System.currentTimeMillis() + "\n"
                + "manufacturer=" + Build.MANUFACTURER + "\n"
                + "model=" + Build.MODEL + "\n"
                + "device=" + Build.DEVICE + "\n"
                + "product=" + Build.PRODUCT + "\n"
                + "fingerprint=" + Build.FINGERPRINT + "\n"
                + "sdk=" + Build.VERSION.SDK_INT + "\n";
    }

    static final class CommandResult {
        final int code;
        final String output;

        CommandResult(int code, String output) {
            this.code = code;
            this.output = output;
        }
    }
}
