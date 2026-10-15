package com.halot455.alice.diag;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

final class SessionStore {
    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences("diag", Context.MODE_PRIVATE);
    }
    static File base(Context c) {
        File dir = new File(c.getFilesDir(), "sessions");
        if (!dir.isDirectory() && !dir.mkdirs()) throw new IllegalStateException("Không tạo được thư mục log");
        return dir;
    }
    static File last(Context c) {
        String name = prefs(c).getString("last", "");
        if (!name.matches("session-[0-9-]+")) return null;
        File dir = new File(base(c), name);
        return dir.isDirectory() ? dir : null;
    }
    static synchronized void append(File dir, String name, String text) throws Exception {
        try (FileOutputStream out = new FileOutputStream(new File(dir, name), true)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
        }
    }
    static synchronized void write(File dir, String name, String text) throws Exception {
        try (FileOutputStream out = new FileOutputStream(new File(dir, name))) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
        }
    }
    static long bytes(File dir) {
        long size = 0;
        File[] files = dir.listFiles();
        if (files != null) for (File file : files) if (file.isFile()) size += file.length();
        return size;
    }
    static synchronized File zip(Context c, File dir) throws Exception {
        File zip = new File(c.getCacheDir(), "ALICE-DIAG-" + dir.getName().substring(8) + ".zip");
        File[] files = dir.listFiles();
        if (files == null) throw new IllegalStateException("Không có log");
        Arrays.sort(files);
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(zip))) {
            byte[] buf = new byte[8192];
            for (File file : files) {
                if (!file.isFile()) continue;
                out.putNextEntry(new ZipEntry(file.getName()));
                try (FileInputStream in = new FileInputStream(file)) {
                    int n;
                    while ((n = in.read(buf)) != -1) out.write(buf, 0, n);
                }
                out.closeEntry();
            }
        }
        return zip;
    }
    static synchronized void deleteSessions(Context c) {
        File[] dirs = base(c).listFiles();
        if (dirs != null) for (File dir : dirs) {
            File[] files = dir.listFiles();
            if (files != null) for (File f : files) if (f.isFile()) f.delete();
            dir.delete();
        }
        File[] cached = c.getCacheDir().listFiles();
        if (cached != null) for (File f : cached) if (f.getName().startsWith("ALICE-DIAG-")) f.delete();
        prefs(c).edit().remove("last").remove("status").apply();
    }
}
