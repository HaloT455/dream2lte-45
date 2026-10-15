package com.halot455.alice.diag;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/** Each read-only command has a deadline and a bounded output buffer. */
final class RootCommand {
    static final int MAX_BYTES = 512 * 1024;
    static final class Result {
        final int code;
        final String output;
        Result(int code, String output) { this.code = code; this.output = output; }
    }
    private static final class LimitedBuffer {
        private final ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        private boolean clipped;
        synchronized void add(byte[] b, int n) {
            int keep = Math.min(n, MAX_BYTES - bytes.size());
            bytes.write(b, 0, keep);
            if (keep < n) clipped = true;
        }
        synchronized String text() {
            return new String(bytes.toByteArray(), StandardCharsets.UTF_8) + (clipped ? "\n[OUTPUT_TRUNCATED]\n" : "");
        }
    }
    static Result run(String script, int timeoutSeconds) {
        Process process = null;
        LimitedBuffer buffer = new LimitedBuffer();
        Thread reader = null;
        try {
            process = new ProcessBuilder("su", "-c", "/system/bin/sh").redirectErrorStream(true).start();
            Process child = process;
            reader = new Thread(() -> {
                try (InputStream in = child.getInputStream()) {
                    byte[] bytes = new byte[4096];
                    int n;
                    while ((n = in.read(bytes)) != -1) buffer.add(bytes, n);
                } catch (Exception ignored) { }
            }, "alice-root-output");
            reader.setDaemon(true);
            reader.start();
            try (OutputStream out = process.getOutputStream()) {
                out.write(script.getBytes(StandardCharsets.UTF_8));
                out.write('\n');
            }
            if (!process.waitFor(timeoutSeconds, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                return new Result(-2, buffer.text() + "\n[COMMAND_TIMEOUT]\n");
            }
            reader.join(500);
            return new Result(process.exitValue(), buffer.text());
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            return new Result(-3, "[COMMAND_CANCELLED]\n");
        } catch (Exception error) {
            return new Result(-1, "[ROOT_UNAVAILABLE " + error.getClass().getSimpleName() + "]\n");
        } finally {
            if (process != null) {
                process.destroyForcibly();
                try { process.getInputStream().close(); } catch (Exception ignored) { }
            }
        }
    }
}
