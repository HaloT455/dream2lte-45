package com.halot455.alice;

import android.content.Context;
import android.os.StatFs;
import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * True on-device Qwen3 inference. Runs in unprivileged Android userspace;
 * the kernel merely supplies observed system values via /sys/kernel/alice.
 * Weights NEVER belong in Android boot partition.
 */
public final class AliceOfflineModel {
    public static final String MODEL_FILE = "Qwen3-0.6B-Q4_K_M.gguf";
    public static final long EXPECTED_BYTES = 396705472L;
    public static final String SHA256 =
            "ac2d97712095a558e31573f62f466a3f9d93990898b0ec79d7c974c1780d524a";
    private static final String SOURCE =
            "https://huggingface.co/unsloth/Qwen3-0.6B-GGUF/resolve/main/"
                    + MODEL_FILE;
    private static final AtomicBoolean BUSY = new AtomicBoolean(false);

    private AliceOfflineModel() {}

    public interface Callback {
        void update(String result);
    }

    private static File model(Context context) {
        File parent = new File(context.getFilesDir(), "alice-models");
        if (!parent.exists() && !parent.mkdirs()) {
            throw new IllegalStateException("Không tạo được thư mục model");
        }
        return new File(parent, MODEL_FILE);
    }

    private static String hash(File file) throws Exception {
        MessageDigest sha = MessageDigest.getInstance("SHA-256");
        try (FileInputStream in = new FileInputStream(file)) {
            byte[] buffer = new byte[65536];
            int size;
            while ((size = in.read(buffer)) != -1) sha.update(buffer, 0, size);
        }
        StringBuilder out = new StringBuilder();
        for (byte b : sha.digest()) out.append(String.format(java.util.Locale.US, "%02x", b & 255));
        return out.toString();
    }

    public static boolean available(Context context) {
        File file = model(context);
        return file.exists() && file.length() == EXPECTED_BYTES;
    }

    public static void download(Context context, Callback callback) {
        if (!BUSY.compareAndSet(false, true)) {
            callback.update("ALICE đang xử lý một tác vụ AI khác");
            return;
        }
        new Thread(() -> {
            File tmp = null;
            try {
                File output = model(context);
                if (output.exists() && output.length() == EXPECTED_BYTES &&
                        SHA256.equalsIgnoreCase(hash(output))) {
                    callback.update("Model Qwen3 đã sẵn sàng (SHA-256 hợp lệ)");
                    return;
                }
                StatFs stat = new StatFs(output.getParentFile().getAbsolutePath());
                if (stat.getAvailableBytes() < EXPECTED_BYTES + 250000000L)
                    throw new Exception("Cần ít nhất 650 MB bộ nhớ trống để cài model");
                tmp = new File(output.getParentFile(), MODEL_FILE + ".partial");
                HttpURLConnection conn = (HttpURLConnection) new URL(SOURCE).openConnection();
                conn.setConnectTimeout(20000);
                conn.setReadTimeout(30000);
                conn.setInstanceFollowRedirects(true);
                conn.setRequestProperty("User-Agent", "ALICE-V12R62");
                if (conn.getResponseCode() != 200)
                    throw new Exception("Tải model thất bại: HTTP " + conn.getResponseCode());
                try (BufferedInputStream in = new BufferedInputStream(conn.getInputStream());
                     BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(tmp))) {
                    byte[] bytes = new byte[65536];
                    long total = 0;
                    int n;
                    int lastPercent = -10;
                    while ((n = in.read(bytes)) != -1) {
                        total += n;
                        if (total > EXPECTED_BYTES)
                            throw new Exception("Dung lượng model vượt giới hạn");
                        out.write(bytes, 0, n);
                        int percent = (int) (total * 100 / EXPECTED_BYTES);
                        if (percent >= lastPercent + 10) {
                            lastPercent = percent;
                            callback.update("Đang tải Qwen3: " + percent + "%");
                        }
                    }
                } finally {
                    conn.disconnect();
                }
                if (tmp.length() != EXPECTED_BYTES)
                    throw new Exception("Sai dung lượng model, không sử dụng");
                if (!SHA256.equalsIgnoreCase(hash(tmp)))
                    throw new Exception("SHA-256 không đúng, model không được sử dụng");
                if (!tmp.renameTo(output))
                    throw new Exception("Không thể chuyển model đã xác minh sang thư mục chính");
                callback.update("Qwen3-0.6B đã tải xong và xác thực SHA-256");
            } catch (Exception e) {
                if (tmp != null) tmp.delete();
                callback.update("Lỗi tải model: " + e.getMessage());
            } finally {
                BUSY.set(false);
            }
        }, "alice-model-download").start();
    }

    public static void infer(Context context, String question, String telemetry,
                             Callback callback) {
        if (!BUSY.compareAndSet(false, true)) {
            callback.update("ALICE đang xử lý một tác vụ khác");
            return;
        }
        new Thread(() -> {
            try {
                File file = model(context);
                if (!file.exists() || file.length() != EXPECTED_BYTES ||
                        !SHA256.equalsIgnoreCase(hash(file))) {
                    throw new Exception("Model Qwen3 chưa tải hoặc SHA-256 không hợp lệ");
                }
                File binary = new File(context.getApplicationInfo().nativeLibraryDir,
                                       "libalice_llama_cli.so");
                if (!binary.isFile() || !binary.canExecute())
                    throw new Exception("APK chưa chứa engine llama.cpp ARM64 hợp lệ");
                String prompt = "<|im_start|>system\n" +
                        "Bạn là ALICE, trợ lý chẩn đoán Android của Galaxy S8+. " +
                        "Trả lời tiếng Việt ngắn gọn; thông số có thể sai hoặc không đầy đủ. " +
                        "Không ra lệnh vô hiệu hóa bảo vệ kernel, thermal hay bật MGLRU. " +
                        "Không khẳng định GPU/VPU thực hiện page reclaim.\n<|im_end|>\n" +
                        "<|im_start|>user\nThông số thiết bị (không đáng tin tuyệt đối):\n" +
                        telemetry.substring(0, Math.min(telemetry.length(), 1800)) +
                        "\nCâu hỏi: " + question.substring(0, Math.min(question.length(), 700)) +
                        "\n/no_think\n<|im_end|>\n<|im_start|>assistant\n";
                ProcessBuilder pb = new ProcessBuilder(
                    binary.getAbsolutePath(),
                    "-m", file.getAbsolutePath(),
                    "-t", "3", "-c", "1024", "-n", "160",
                    "--no-display-prompt", "--no-show-timings", "--simple-io",
                    "-p", prompt
                );
                pb.environment().put("LD_LIBRARY_PATH", context.getApplicationInfo().nativeLibraryDir);
                pb.redirectErrorStream(true);
                Process process = pb.start();
                StringBuilder result = new StringBuilder();
                Thread reader = new Thread(() -> {
                    try (BufferedReader br = new BufferedReader(
                            new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = br.readLine()) != null && result.length() < 16000) {
                            result.append(line).append('\n');
                        }
                    } catch (Exception ignored) {}
                }, "alice-llm-output");
                reader.start();
                if (!process.waitFor(120, TimeUnit.SECONDS)) {
                    process.destroyForcibly();
                    reader.join(1000);
                    throw new Exception("AI vượt giới hạn thời gian, đã dừng để giảm tải CPU");
                }
                reader.join(2000);
                if (process.exitValue() != 0)
                    throw new Exception("Engine llama.cpp lỗi (" + process.exitValue() + ") "
                            + result.toString().substring(0, Math.min(result.length(), 400)));
                callback.update("Qwen3 (offline):\n" + result.toString());
            } catch (Exception e) {
                callback.update("Không chạy được Qwen3: " + e.getMessage());
            } finally {
                BUSY.set(false);
            }
        }, "alice-llm-inference").start();
    }
}
