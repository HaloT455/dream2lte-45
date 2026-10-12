package com.halot455.alice;

import android.content.Context;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/**
 * Exynos8895 MGLRU process guard. The Qwen3 model cannot send raw shell commands.
 * Root can only call the checked, packaged script with an allowlisted subcommand.
 * Root transactions are serialized by the shell lock, but RESTORE must not wait
 * for an ongoing 8-second trial in Java. WARNING: no userspace watchdog can
 * recover a kernel deadlock.
 */
public final class AliceMglruGuard {
    private AliceMglruGuard() {}
    private static synchronized File helper(Context context) throws Exception {
        File file = new File(context.getFilesDir(), "alice_mglru_guard.sh");
        File staging = new File(context.getFilesDir(), "alice_mglru_guard.tmp");
        try (InputStream in = context.getAssets().open("alice_mglru_guard.sh");
             FileOutputStream out = new FileOutputStream(staging)) {
            byte[] buf = new byte[8192];
            int count;
            while ((count = in.read(buf)) != -1) out.write(buf, 0, count);
        }
        if (!staging.renameTo(file)) {
            file.delete();
            if (!staging.renameTo(file)) throw new Exception("Không lưu được MGLRU guard");
        }
        file.setReadable(true, true);
        file.setWritable(true, true);
        return file;
    }

    public static String root(Context context, String command) throws Exception {
        if (!"status".equals(command) && !"probe".equals(command)
                && !"manual".equals(command) && !"auto".equals(command)
                && !"restore".equals(command))
            throw new IllegalArgumentException("Lệnh MGLRU không cho phép");
        String path = helper(context).getAbsolutePath();
        if (!path.matches("/data/user(/[0-9]+)?/.*|/data/data/.*"))
            throw new SecurityException("Đường dẫn bất thường");
        Process process = new ProcessBuilder("su", "-c",
                "/system/bin/sh " + path + " " + command)
                .redirectErrorStream(true).start();
        int waitSeconds = ("manual".equals(command) || "auto".equals(command)) ? 26 : 12;
        if (!process.waitFor(waitSeconds, TimeUnit.SECONDS)) {
            process.destroyForcibly();
            throw new Exception("Kernel/tiến trình không trả lời; không bảo đảm phục hồi");
        }
        StringBuilder out = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null && out.length() < 15000)
                out.append(line).append('\n');
        }
        String text = out.toString().trim();
        if (process.exitValue() != 0) throw new Exception(text);
        return text;
    }
}
