package vn.alice.uitrace;

import java.io.File;
import java.io.IOException;

final class SafeFiles {
    static String quote(String value) {
        if (value.indexOf('\0') >= 0) throw new IllegalArgumentException("NUL in path");
        return "'" + value.replace("'", "'\"'\"'") + "'";
    }

    static File log(File directory, String name) throws IOException {
        if (name == null || !name.matches("ui-trace-[0-9]{8}-[0-9]{6}-[0-9]+\\.txt"))
            throw new IOException("Invalid log name");
        File root = directory.getCanonicalFile();
        File file = new File(root, name).getCanonicalFile();
        if (!root.equals(file.getParentFile())) throw new IOException("Log path escaped");
        return file;
    }

    static String stopCommand(long pid, File script) {
        if (pid <= 1 || pid > Integer.MAX_VALUE) throw new IllegalArgumentException("Invalid pid");
        return "if grep -Fq -- " + quote(script.getAbsolutePath()) + " /proc/" + pid
            + "/cmdline; then kill -TERM " + pid + "; fi";
    }
}
