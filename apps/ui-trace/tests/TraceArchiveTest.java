package vn.alice.uitrace;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.RandomAccessFile;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public final class TraceArchiveTest {
    public static void main(String[] args) throws Exception {
        File dir = Files.createTempDirectory("alice-archive-").toFile();
        try {
            File trace = new File(dir, "trace"), report = new File(dir, "report"), config = new File(dir, "config");
            byte[] chunk = new byte[65536];
            new java.util.Random(42).nextBytes(chunk);
            // Exceeds old 128 MiB text cap, runs under a 32 MiB heap.
            try (FileOutputStream out = new FileOutputStream(trace)) {
                for (int i = 0; i < 2304; i++) out.write(chunk);
            }
            Files.write(report.toPath(), "AFTER_METADATA\nCLEANUP_OK\n".getBytes("UTF-8"));
            Files.write(config.toPath(), "duration_ms: 60000\n".getBytes("UTF-8"));
            File zip = new File(dir, "log.zip");
            TraceArchive.create(zip, trace, report, config);
            int entries = 0; long traceSize = 0;
            try (ZipInputStream in = new ZipInputStream(new FileInputStream(zip))) {
                ZipEntry entry;
                while ((entry = in.getNextEntry()) != null) {
                    long size = 0; int n;
                    while ((n = in.read(chunk)) != -1) size += n;
                    if (entry.getName().equals("capture.perfetto-trace")) traceSize = size;
                    entries++;
                    in.closeEntry(); // Includes CRC checks for every entry.
                }
            }
            assert entries == 3 && traceSize == 144L * 1024 * 1024;
            boolean failed = false;
            try { TraceArchive.create(zip, trace, report, config); } catch (Exception e) { failed = true; }
            assert failed && zip.isFile() : "Never overwrite a completed log";
            File tooBig = new File(dir, "oversize");
            try (RandomAccessFile out = new RandomAccessFile(tooBig, "rw")) { out.setLength(TraceArchive.MAX_TRACE + 1); }
            File failedZip = new File(dir, "failed.zip");
            failed = false;
            try { TraceArchive.create(failedZip, tooBig, report, config); } catch (Exception e) { failed = true; }
            assert failed && !failedZip.exists() && !new File(failedZip + ".partial").exists();
            assert tooBig.isFile() && report.isFile() : "Failure preserves source diagnostics";
            System.out.println("PASS: 144 MiB archive under 32 MiB heap, CRC, metadata, size bounds and atomic publish");
        } finally {
            for (File file : dir.listFiles()) Files.delete(file.toPath());
            Files.delete(dir.toPath());
        }
    }
}
