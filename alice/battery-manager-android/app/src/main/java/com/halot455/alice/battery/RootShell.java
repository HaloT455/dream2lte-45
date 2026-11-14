package com.halot455.alice.battery;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.concurrent.TimeUnit;

/** Fixed allow-listed root operations. No arbitrary commands from user input. */
public final class RootShell {
    private RootShell() {}
    public static final class Result {
        public final boolean success;
        public final String output;
        Result(boolean ok, String output) { this.success=ok; this.output=output; }
    }
    private static Result execute(String constantCommand, long timeoutSeconds) {
        Process process=null;
        try {
            process=new ProcessBuilder("su","-c",constantCommand)
                    .redirectErrorStream(true).start();
            boolean completed=process.waitFor(timeoutSeconds,TimeUnit.SECONDS);
            if (!completed) {
                process.destroyForcibly();
                return new Result(false,"Không nhận được phản hồi từ su");
            }
            StringBuilder msg=new StringBuilder();
            try (BufferedReader br=new BufferedReader(new InputStreamReader(
                    process.getInputStream()))) {
                String line;
                while ((line=br.readLine())!=null && msg.length()<600)
                    msg.append(line).append(' ');
            }
            return new Result(process.exitValue()==0,msg.toString().trim());
        } catch (Exception e) {
            return new Result(false,e.getClass().getSimpleName());
        } finally {
            if (process!=null) process.destroy();
        }
    }
    public static boolean isRootGranted() {
        Result r=execute("id -u",30);
        return r.success && "0".equals(r.output.trim());
    }
    public static Result setStandardBatterySaver(boolean enabled) {
        // cmd power set-mode is the standard Android Battery Saver command.
        // Samsung-specific UPSM is deliberately NOT claimed or spoofed here.
        return execute(enabled?"cmd power set-mode 1":"cmd power set-mode 0",6);
    }
}
