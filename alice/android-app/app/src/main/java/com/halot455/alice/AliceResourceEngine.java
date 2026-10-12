package com.halot455.alice;

import android.content.Context;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/**
 * ALICE resource allocator (measured heuristics, not the Qwen language model).
 * Kernel MGLRU is still CPU-only. LMKD retains authority to kill cached apps.
 * All writable actions are allowlisted in bundled root helper.
 */
public final class AliceResourceEngine {
    public static final class Sample {
        public final long totalKb, availableKb, swapTotalKb, swapFreeKb, refaults;
        public final double some10, full10;
        public final boolean valid;
        public final String error;
        private Sample(long total,long avail,long swap,long free,long refault,
                       double some,double full,boolean good,String err) {
            totalKb=total;availableKb=avail;swapTotalKb=swap;swapFreeKb=free;
            refaults=refault;some10=some;full10=full;valid=good;error=err;
        }
        public double availablePercent() {
            return totalKb > 0 ? 100.0 * availableKb / totalKb : 0;
        }
        public double swapUsedPercent() {
            return swapTotalKb > 0 ? 100.0*(swapTotalKb-swapFreeKb)/swapTotalKb : 0;
        }
        public String summary() {
            if (!valid) return "Không đọc được tài nguyên: "+error;
            return String.format(java.util.Locale.US,
                "MemAvailable %.1f%% (%d MB); zRAM/swap %.1f%% used; "
                + "PSI some %.2f%%, full %.2f%% (avg10); refault=%d",
                availablePercent(),availableKb/1024,swapUsedPercent(),
                some10,full10,refaults);
        }
    }
    public static final class Decision {
        public final int mode;
        public final String tier, reason;
        public final boolean highPressure;
        private Decision(int m,String t,String r,boolean h) {
            mode=m;tier=t;reason=r;highPressure=h;
        }
        public String explain() { return tier+" / "+reason+" / đề xuất mode="+mode; }
    }

    private AliceResourceEngine() {}
    private static String read(String file, int maxChars) {
        StringBuilder out = new StringBuilder();
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String line;
            while ((line=r.readLine())!=null && out.length()<maxChars)
                out.append(line).append('\n');
        } catch (Exception e) {
            return "";
        }
        return out.toString();
    }
    private static long metric(String meminfo,String key) {
        for (String line:meminfo.split("\n")) {
            if (!line.startsWith(key+":")) continue;
            String[] f=line.substring(key.length()+1).trim().split("\\s+");
            try { return Long.parseLong(f[0]); } catch (Exception ignored) {}
        }
        return -1;
    }
    private static double psiValue(String line) {
        String[] v = line.trim().split("\\s+");
        for (String item:v) if (item.startsWith("avg10=")) {
            try { return Double.parseDouble(item.substring(6)); }
            catch(Exception ignored) { return -1; }
        }
        return -1;
    }
    private static long refaults(String vmstat) {
        long count=0;
        for (String line:vmstat.split("\n")) {
            if (!line.startsWith("workingset_refault")) continue;
            String[] f=line.split("\\s+");
            try { count+=Long.parseLong(f[f.length-1]); }
            catch(Exception ignored) {}
        }
        return count;
    }
    public static Sample sample() {
        String mem=read("/proc/meminfo",16000);
        String psi=read("/proc/pressure/memory",2000);
        String vm=read("/proc/vmstat",18000);
        long total=metric(mem,"MemTotal"), available=metric(mem,"MemAvailable");
        long swap=metric(mem,"SwapTotal"), free=metric(mem,"SwapFree");
        double some=-1,full=-1;
        for(String line:psi.split("\n")) {
            if(line.startsWith("some "))some=psiValue(line);
            if(line.startsWith("full "))full=psiValue(line);
        }
        boolean ok=total>0 && available>=0 && swap>=0 && free>=0
                && some>=0 && full>=0;
        return new Sample(total,available,swap,free,refaults(vm),
                some,full,ok, ok?null:"thiếu /proc/meminfo hoặc PSI");
    }

    /**
     * Reserved stability 4 under contention. Never raise CPU frequencies or
     * force MGLRU. Swappiness policy is applied separately by the kernel only
     * if the user explicitly enrolled.
     */
    public static Decision choose(Sample s, Sample previous) {
        if(!s.valid) return new Decision(4,"NO_DATA","bảo vệ hệ thống, không chỉnh",true);
        boolean critical = s.full10>=5 || s.some10>=35
                || (s.availablePercent()<6 && s.swapUsedPercent()>=85);
        if(critical) return new Decision(4,"CRITICAL",
            "PSI full/thiếu RAM cao: ưu tiên ổn định và LMKD mặc định",true);
        boolean pressure = s.full10>=1.5 || s.some10>=15
                || s.availablePercent()<10
                || (s.swapTotalKb>0 && s.swapUsedPercent()>80);
        if(pressure) return new Decision(4,"PRESSURE",
            "giảm điều chỉnh; để LMKD xử lý app cache khi cần",true);
        if(previous != null && previous.valid
                && s.refaults>previous.refaults+10000 && s.some10>=5)
            return new Decision(4,"THRASH",
                "workingset refault tăng nhanh, tránh reclaim thử nghiệm",true);
        return new Decision(0,"BALANCED",
            "áp lực thấp: giữ governor/thermal và LMKD Android",false);
    }

    private static synchronized File helper(Context ctx) throws Exception {
        File f = new File(ctx.getFilesDir(),"alice_memory.sh");
        File tmp = new File(ctx.getFilesDir(),"alice_memory.tmp");
        try(InputStream input=ctx.getAssets().open("alice_memory.sh");
            FileOutputStream out=new FileOutputStream(tmp,false)){
            byte[] buf=new byte[8192];int n;
            while((n=input.read(buf))!=-1)out.write(buf,0,n);
        }
        if(!tmp.renameTo(f)){
            f.delete();
            if(!tmp.renameTo(f))throw new Exception("Không lưu được ALICE helper");
        }
        f.setReadable(true,true);
        f.setWritable(true,true);
        return f;
    }
    public static synchronized String root(Context ctx,String operation,int number) throws Exception {
        switch(operation) {
            case "status":case "capability":case "policy-on":case "policy-off":
            case "restore":case "mglru-trial":break;
            case "mode":
                if(number<0||number>5) throw new Exception("Profile không hợp lệ");
                break;
            case "lmkd-trial":
                if(number<35||number>100)throw new Exception("LMKD ngoài phạm vi");
                break;
            default: throw new Exception("ALICE từ chối lệnh ngoài danh sách");
        }
        String path=helper(ctx).getAbsolutePath();
        if(!path.matches("/data/user(/[0-9]+)?/.*|/data/data/.*"))
            throw new SecurityException("Helper path invalid");
        String cmd="/system/bin/sh "+path+" "+operation;
        if(operation.equals("mode")||operation.equals("lmkd-trial"))
            cmd+=" "+number;
        Process p = new ProcessBuilder("su","-c",cmd).redirectErrorStream(true).start();
        int seconds=operation.equals("lmkd-trial")?38:
            (operation.equals("mglru-trial")?27:15);
        if(!p.waitFor(seconds,TimeUnit.SECONDS)){
            p.destroyForcibly();
            throw new Exception("Lệnh quá thời gian; có thể cần khôi phục thủ công");
        }
        StringBuilder output=new StringBuilder();
        try(BufferedReader reader=new BufferedReader(
                new InputStreamReader(p.getInputStream(),StandardCharsets.UTF_8))){
            String ln;
            while((ln=reader.readLine())!=null && output.length()<22000)
                output.append(ln).append('\n');
        }
        if(p.exitValue()!=0)
            throw new Exception("ALICE từ chối / root lỗi: "+output.toString().trim());
        return output.toString();
    }
}
