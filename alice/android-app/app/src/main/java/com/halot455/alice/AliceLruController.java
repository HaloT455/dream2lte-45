package com.halot455.alice;

import android.content.Context;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Fixed, packaged LRU commands. Output is drained while waiting for root. */
public final class AliceLruController {
    private AliceLruController() {}

    public static final class Result {
        public final int code;
        public final String text;
        Result(int code, String text) { this.code = code; this.text = text; }
    }

    private static synchronized File helper(Context context) throws Exception {
        File file = new File(context.getFilesDir(), "alice_lru.sh");
        File staging = new File(context.getFilesDir(), "alice_lru.tmp");
        try (InputStream in = context.getAssets().open("alice_lru.sh");
             FileOutputStream out = new FileOutputStream(staging)) {
            byte[] bytes = new byte[8192];
            int count;
            while ((count = in.read(bytes)) != -1) out.write(bytes, 0, count);
        }
        if (!staging.renameTo(file)) throw new Exception("Không lưu được bộ điều khiển LRU");
        file.setReadable(true, true);
        file.setWritable(true, true);
        return file;
    }

    public static Result run(Context context, String action) throws Exception {
        if (!"status".equals(action) && !"on".equals(action)
                && !"off".equals(action) && !"trial".equals(action))
            throw new IllegalArgumentException("Lệnh LRU không hợp lệ");
        String path = helper(context).getAbsolutePath();
        // Context supplies this private path; quoting also handles unusual paths.
        String quoted = "'" + path.replace("'", "'\\''") + "'";
        Process process = new ProcessBuilder("su", "-c",
                "/system/bin/sh " + quoted + " " + action).redirectErrorStream(true).start();
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        AtomicReference<Exception> readError = new AtomicReference<>();
        Thread reader = new Thread(() -> {
            try (InputStream in = process.getInputStream()) {
                byte[] buffer = new byte[4096];
                int count;
                while ((count = in.read(buffer)) != -1) {
                    int keep = Math.min(count, 96000 - bytes.size());
                    if (keep > 0) bytes.write(buffer, 0, keep);
                    // Continue draining after the capture limit to avoid a full pipe.
                }
            } catch (Exception e) { readError.set(e); }
        }, "alice-lru-output");
        reader.setDaemon(true);
        reader.start();
        boolean done;
        try {
            done = process.waitFor("trial".equals(action) ? 35 : 25, TimeUnit.SECONDS);
            if (!done) process.destroyForcibly();
            reader.join(2000);
            if (reader.isAlive()) {
                process.getInputStream().close();
                reader.join(1000);
            }
        } catch (InterruptedException e) {
            process.destroyForcibly();
            process.getInputStream().close();
            Thread.currentThread().interrupt();
            throw e;
        }
        String output = new String(bytes.toByteArray(), StandardCharsets.UTF_8).trim();
        if (!done) return new Result(-1, output + "\nHết thời gian chờ; chưa xác nhận trạng thái kernel.");
        if (readError.get() != null) output += "\nKhông đọc hết được log: " + readError.get().getMessage();
        return new Result(process.exitValue(), output);
    }
}
