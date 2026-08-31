package vn.alice.uitrace;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Constant-memory archive; a partial ZIP is never advertised as a saved log. */
final class TraceArchive {
    static final long MAX_TRACE = 256L * 1024 * 1024;
    static void create(File destination, File trace, File report, File config) throws IOException {
        if (destination.exists()) throw new IOException("Archive already exists");
        File pending = new File(destination.getPath() + ".partial");
        if (!pending.createNewFile()) throw new IOException("Pending archive already exists");
        boolean done = false;
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new BufferedOutputStream(new FileOutputStream(pending), 65536))) {
                zip.setLevel(1); // After recording only; never compress on UI/tracing threads.
                add(zip, "capture.perfetto-trace", trace, MAX_TRACE);
                add(zip, "metadata.txt", report, 8L * 1024 * 1024);
                add(zip, "config.pbtxt", config, 65536);
            }
            if (!pending.renameTo(destination)) throw new IOException("Cannot finalize archive");
            done = true;
        } finally {
            if (!done) pending.delete(); // This operation's incomplete output only; sources preserved.
        }
    }
    private static void add(ZipOutputStream zip, String name, File source, long limit) throws IOException {
        if (!source.isFile() || source.length() > limit) throw new IOException("Invalid/oversized " + name);
        zip.putNextEntry(new ZipEntry(name));
        byte[] bytes = new byte[65536]; long copied = 0;
        try (FileInputStream input = new FileInputStream(source)) {
            int n;
            while ((n = input.read(bytes)) != -1) {
                copied += n;
                if (copied > limit) throw new IOException("Growing/oversized " + name);
                zip.write(bytes, 0, n);
            }
        }
        zip.closeEntry();
    }
}
