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
    /** Read-only sysfs bridge when the Samsung ROM masks kernel attributes from apps.
     *  Runs one fixed, allow-listed command under the user's approved su grant.
     */
    public static final class KernelSnapshot {
        public final boolean valid;
        public final int real, normal, display, emergency, fullSeen;
        KernelSnapshot(boolean valid, int real, int normal, int display, int emergency, int fullSeen) {
            this.valid=valid; this.real=real; this.normal=normal;
            this.display=display; this.emergency=emergency; this.fullSeen=fullSeen;
        }
    }

    public static KernelSnapshot readKernelReserve() {
        final String readOnly =
                "for n in real_percent normal_percent display_percent emergency_active full_charge_seen; do " +
                "cat /sys/kernel/alice_battery_reserve/$n 2>/dev/null || echo -1; done";
        Result r=execute(readOnly,6);
        if (r.success) {
            try {
                String[] fields=r.output.trim().split("\\s+");
                if (fields.length==5) {
                    int[] v=new int[5];
                    for (int i=0;i<5;i++) v[i]=Integer.parseInt(fields[i]);
                    if (v[0]>=0 && v[0]<=100 && v[1]>=0 && v[1]<=100 &&
                        v[2]>=0 && v[2]<=100 && (v[3]==0 || v[3]==1) &&
                        (v[4]==0 || v[4]==1)) {
                        return new KernelSnapshot(true,v[0],v[1],v[2],v[3],v[4]);
                    }
                }
            } catch (NumberFormatException ignored) {}
        }
        return new KernelSnapshot(false,-1,-1,-1,-1,-1);
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
