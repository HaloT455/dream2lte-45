package com.halo.mglrudiag;

import android.content.Context;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

final class RootUtil {
    private RootUtil() {}

    static final class Result {
        final int code;
        final String output;
        Result(int code, String output) {
            this.code = code;
            this.output = output;
        }
    }

    static File marker(Context context) {
        return new File(context.getFilesDir(), "active_session.txt");
    }

    static void writeActiveSession(Context context, String path) throws IOException {
        try (FileOutputStream out = new FileOutputStream(marker(context), false)) {
            out.write((path + "\n").getBytes(StandardCharsets.UTF_8));
            out.getFD().sync();
        }
    }

    static String readActiveSession(Context context) {
        File file = marker(context);
        if (!file.isFile())
            return null;
        try (BufferedReader br = new BufferedReader(new FileReader(file))) {
            String line = br.readLine();
            return line == null || line.trim().isEmpty() ? null : line.trim();
        } catch (IOException e) {
            return null;
        }
    }

    static void clearActiveSession(Context context) {
        //noinspection ResultOfMethodCallIgnored
        marker(context).delete();
    }

    static File ensureLoggerScript(Context context) throws IOException {
        File outFile = new File(context.getFilesDir(), "mglru_logger.sh");
        try (InputStream in = context.getAssets().open("logger.sh");
             OutputStream out = new FileOutputStream(outFile, false)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0)
                out.write(buf, 0, n);
        }
        //noinspection ResultOfMethodCallIgnored
        outFile.setExecutable(true, true);
        return outFile;
    }

    static String shQuote(String value) {
        return "'" + value.replace("'", "'\\''") + "'";
    }

    static Result execRoot(String command) {
        StringBuilder output = new StringBuilder();
        try {
            Process p = new ProcessBuilder("su", "-c", command)
                    .redirectErrorStream(true)
                    .start();
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = br.readLine()) != null)
                    output.append(line).append('\n');
            }
            int code = p.waitFor();
            return new Result(code, output.toString());
        } catch (Exception e) {
            return new Result(-1, e.toString());
        }
    }
}
