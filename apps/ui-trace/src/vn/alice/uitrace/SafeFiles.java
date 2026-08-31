package vn.alice.uitrace;

import java.io.File;
import java.io.IOException;

final class SafeFiles {
    static String quote(String value) {
        if (value.indexOf('\0') >= 0) throw new IllegalArgumentException("NUL in path");
        return "'" + value.replace("'", "'\"'\"'") + "'";
    }

    static File log(File directory, String name) throws IOException {
        if (!validLogName(name))
            throw new IOException("Invalid log name");
        File root = directory.getCanonicalFile();
        File file = new File(root, name).getCanonicalFile();
        if (!root.equals(file.getParentFile())) throw new IOException("Log path escaped");
        return file;
    }

    static boolean validLogName(String name) {
        return name != null && name.matches("ui-trace-[0-9]{8}-[0-9]{6}-[0-9]+\\.(txt|zip)");
    }

    static String mimeType(String name) { return name != null && name.endsWith(".zip") ? "application/zip" : "text/plain"; }

    static String stopCommand(long pid, File script) {
        if (pid <= 1 || pid > Integer.MAX_VALUE) throw new IllegalArgumentException("Invalid pid");
        return "if tr '\\000' '\\n' < /proc/" + pid + "/cmdline | grep -Fxq -- "
            + quote(script.getAbsolutePath()) + "; then kill -TERM " + pid + "; fi";
    }
}
