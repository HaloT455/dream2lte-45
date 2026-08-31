package vn.alice.uitrace;
import java.io.File;
import java.nio.file.Files;

public final class SafeFilesTest {
    public static void main(String[] args) throws Exception {
        File dir = Files.createTempDirectory("alice-safe-").toFile();
        try {
            assert SafeFiles.log(dir, "ui-trace-20260831-040000-12345.txt").getParentFile().equals(dir.getCanonicalFile());
            assert SafeFiles.log(dir, "ui-trace-20260831-040000-12345.zip").getParentFile().equals(dir.getCanonicalFile());
            assert !SafeFiles.validLogName("ui-trace-20260831-040000-12345.zip.partial");
            assert SafeFiles.mimeType("x.zip").equals("application/zip");
            assert SafeFiles.mimeType("x.txt").equals("text/plain");
            for (String name : new String[]{"../secret", "a.txt", "/data/secret", "ui-trace-20260831-040000-12345.txt/../secret"}) {
                boolean failed = false; try { SafeFiles.log(dir, name); } catch (Exception e) { failed = true; }
                assert failed : name;
            }
            assert SafeFiles.quote("a'b").equals("'a'\"'\"'b'");
            assert SafeFiles.stopCommand(123, new File(dir, "capture-123.sh")).contains("/proc/123/cmdline");
            assert SafeFiles.stopCommand(123, new File(dir, "capture-123.sh")).contains("grep -Fxq");
            for (long pid : new long[]{-1, 0, 1, Long.MAX_VALUE}) {
                boolean failed = false; try { SafeFiles.stopCommand(pid, dir); } catch (IllegalArgumentException e) { failed = true; }
                assert failed;
            }
            System.out.println("PASS: log path containment, shell quoting and owned PID validation");
        } finally { Files.delete(dir.toPath()); }
    }
}
