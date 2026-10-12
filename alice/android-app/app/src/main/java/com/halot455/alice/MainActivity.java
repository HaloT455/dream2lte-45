package com.halot455.alice;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Locale;

public final class MainActivity extends Activity implements TextToSpeech.OnInitListener {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView dashboard, reply, processesPanel;
    private volatile AliceProcessEngine.Snapshot lastProcessSnapshot;
    private TextToSpeech tts;
    private boolean active;
    private static final int SPEECH_REQUEST = 801;
    private static final int NAVY = Color.rgb(11, 28, 61);
    private final Runnable poll = new Runnable() {
        @Override public void run() {
            if (!active) return;
            if (dashboard != null) dashboard.setText(buildReport());
            handler.postDelayed(this, 15000);
        }
    };

    private TextView text(String s, int size, boolean bold) {
        TextView v = new TextView(this);
        v.setText(s);
        v.setTextSize(size);
        v.setTextColor(NAVY);
        v.setPadding(14, 10, 14, 10);
        if (bold) v.setTypeface(null, Typeface.BOLD);
        return v;
    }
    private Button button(LinearLayout layout, String label, View.OnClickListener onClick) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setOnClickListener(onClick);
        layout.addView(b, new LinearLayout.LayoutParams(-1, -2));
        return b;
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView sc = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(20, 24, 20, 24);
        root.setBackgroundColor(Color.WHITE);
        sc.addView(root); setContentView(sc);
        root.addView(text("ALICE • System Intelligence + Qwen3", 24, true));
        root.addView(text("Exynos 8895 | V12R61 boot kernel + Qwen3 AI offline", 13, false));
        dashboard = text("Reading telemetry…", 14, false);
        dashboard.setTextIsSelectable(true);
        root.addView(dashboard);
        button(root, "Làm mới thông số", v -> dashboard.setText(buildReport()));
        button(root, "Đọc ALICE qua KernelSU (nếu bị chặn)", v -> refreshWithRoot());
        root.addView(text("Chế độ trực tiếp trong kernel (root KernelSU)", 18, true));
        final String[] modes = {"balanced","performance","gaming","battery","stability","research"};
        for (String mode : modes) button(root, "Chọn " + mode, v -> confirmMode(mode));
        button(root, "Bật tối ưu VM có giới hạn (thủ công)", v -> confirmRoot("Bật vm.swappiness",
                "printf 1 > /sys/kernel/alice/policy_enabled"));
        button(root, "Tắt tối ưu và phục hồi VM", v -> confirmRoot("Tắt chính sách VM và phục hồi",
                "printf 0 > /sys/kernel/alice/policy_enabled"));
        root.addView(text("ALICE AI quản lý tiến trình (quyền root)", 18, true));
        processesPanel = text("Chưa quét. ALICE chỉ điều chỉnh ứng dụng nền, không kill tiến trình.", 13, false);
        processesPanel.setTextIsSelectable(true);
        root.addView(processesPanel);
        button(root, "Quét RAM / CPU / tiến trình theo PID", v -> scanProcesses());
        button(root, "Để Qwen3 phân tích tiến trình thật", v -> analyzeProcesses());
        button(root, "Chọn ứng dụng nền để giảm ưu tiên CPU", v -> chooseProcessToLimit());
        button(root, "Bật quản lý tiến trình nền tự động", v -> confirmAutoProcess());
        button(root, "Dừng quản lý tự động và khôi phục", v -> stopAutoProcess());
        button(root, "Khôi phục toàn bộ mức ưu tiên", v -> restoreProcesses());
        root.addView(text("Các chức năng thực sự qua ALICE", 18, true));
        root.addView(text(featureMatrix(), 13, false));
        root.addView(text("Qwen3 0.6B - Mô hình AI thật, chạy offline", 18, true));
        button(root, "Tải Qwen3 ~397 MB và xác thực SHA-256", v -> {
            reply.setText("Đang chuẩn bị tải mô hình vào bộ nhớ ứng dụng...");
            AliceOfflineModel.download(this, msg -> runOnUiThread(() -> reply.setText(msg)));
        });
        button(root, "Chat trực tiếp với ALICE Qwen3 offline", v -> askQwenDialog());
        root.addView(text("ALICE Trợ lý chẩn đoán", 18, true));
        reply = text("ALICE offline phân tích theo quy tắc, không phải LLM.",14,false);
        root.addView(reply);
        button(root, "Đặt câu hỏi cho Alice", v -> askDialog());
        button(root, "Điều khiển bằng giọng nói", v -> speech());
        button(root, "ChatGPT online (mở trình duyệt)", v -> {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse("https://chatgpt.com/"));
            try { startActivity(i); } catch (Exception e) { toast("Không có trình duyệt"); }
        });
        button(root, "Xuất báo cáo chẩn đoán", v -> {
            Intent i = new Intent(Intent.ACTION_SEND);
            i.setType("text/plain");
            i.putExtra(Intent.EXTRA_TEXT, buildReport());
            startActivity(Intent.createChooser(i,"Chia sẻ báo cáo ALICE"));
        });
        root.addView(text("An toàn: MGLRU mặc định OFF. Ứng dụng không tự bật MGLRU, ép xung, "
                + "tắt thermal/SELinux hoặc thay DTB. GPU/VPU không thể thu hồi trang RAM thay kernel CPU.",12,false));
        tts = new TextToSpeech(this, this);
    }
    private static String read(String path, int limit) {
        try (BufferedReader reader = new BufferedReader(new FileReader(path))) {
            StringBuilder out=new StringBuilder(); String s;
            while ((s=reader.readLine())!=null && out.length()<limit) out.append(s).append('\n');
            return out.toString().trim();
        } catch (Exception ignored) { return "Không truy cập được"; }
    }
    private static String memInfo() {
        StringBuilder b=new StringBuilder();
        try (BufferedReader reader=new BufferedReader(new FileReader("/proc/meminfo"))) {
            String s; while ((s=reader.readLine())!=null) {
                if (s.startsWith("MemTotal:") || s.startsWith("MemAvailable:") ||
                    s.startsWith("SwapTotal:") || s.startsWith("SwapFree:")) b.append(s).append('\n');
            }
        } catch (IOException ignored) {}
        return b.toString();
    }
    private static String cpuFreq(int cpu) {
        return read("/sys/devices/system/cpu/cpu"+cpu+"/cpufreq/scaling_cur_freq",64);
    }
    private static String battery() {
        String val=read("/sys/class/power_supply/battery/temp",30);
        try { return (Long.parseLong(val)/10f)+"°C"; } catch (Exception ignored) {return "?";}
    }
    private void refreshWithRoot() {
        dashboard.setText("Đang đọc từ kernel qua quyền root…");
        new Thread(() -> {
            /* Fixed, read-only path list: no user input reaches the shell. */
            String command = "for n in version safety capabilities assessment "
                    + "mm_reclaim memory mode vm_policy policy_enabled; do "
                    + "echo ===$n===; cat /sys/kernel/alice/$n 2>/dev/null; done";
            String result;
            try {
                Process p = new ProcessBuilder("su", "-c", command)
                        .redirectErrorStream(true).start();
                if (!p.waitFor(15, java.util.concurrent.TimeUnit.SECONDS)) {
                    p.destroyForcibly();
                    result = "KernelSU chưa cấp quyền hoặc đọc quá thời gian.";
                } else if (p.exitValue() != 0) {
                    result = "Không thể đọc ALICE. Kiểm tra kernel V12R61 và cấp root.";
                } else {
                    StringBuilder out = new StringBuilder();
                    try (BufferedReader br = new BufferedReader(
                            new java.io.InputStreamReader(p.getInputStream(),
                                    StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = br.readLine()) != null && out.length() < 6000)
                            out.append(line).append('\n');
                    }
                    result = out.toString();
                }
            } catch (Exception e) {
                result = "Không thể dùng su: " + e.getClass().getSimpleName();
            }
            final String shown = result;
            runOnUiThread(() -> {
                if (dashboard != null) dashboard.setText(shown);
            });
        }, "alice-root-reader").start();
    }

    private String buildReport() {
        boolean bridge = new File("/sys/kernel/alice/version").exists();
        StringBuilder s=new StringBuilder();
        s.append("ALICE kernel bridge: ").append(bridge?"Phát hiện":"Chưa có hoặc bị chặn").append('\n');
        if (bridge) {
            s.append(read("/sys/kernel/alice/version",150)).append('\n');
            s.append("Reclaim: ").append(read("/sys/kernel/alice/mm_reclaim",700)).append('\n');
            s.append("Phân tích: ").append(read("/sys/kernel/alice/assessment",400)).append('\n');
            s.append("Năng lực: ").append(read("/sys/kernel/alice/capabilities",500)).append('\n');
            s.append("Cấu hình: ").append(read("/sys/kernel/alice/vm_policy",350)).append('\n');
            s.append("Safe: ").append(read("/sys/kernel/alice/safety",200)).append('\n');
        }
        s.append("MGLRU: ").append(read("/sys/kernel/mm/lru_gen/enabled",60)).append('\n');
        s.append(memInfo());
        s.append("PSI memory:\n").append(read("/proc/pressure/memory",600)).append('\n');
        s.append("CPU 0 / 4 (kHz): ").append(cpuFreq(0)).append(" / ").append(cpuFreq(4)).append('\n');
        s.append("GPU clock (driver unit): ").append(read("/sys/kernel/gpu/gpu_clock",60)).append('\n');
        s.append("VPU /dev/vertex: ").append(new File("/dev/vertex").exists()?"present":"missing/hidden").append('\n');
        s.append("Battery temp: ").append(battery()).append('\n');
        s.append("Kernel: ").append(read("/proc/sys/kernel/osrelease",140));
        return s.toString();
    }

    private String featureMatrix() {
        return "KERNEL / HOẠT ĐỘNG THẬT\n"
             + "• CPU: theo dõi xung; giữ DVFS V12R5T, không tự ép xung\n"
             + "• RAM + zRAM + PSI: giám sát và phân loại áp lực bằng quy tắc\n"
             + "• Tiến trình: quét PID/RSS/CPU ticks/oom_adj, AI chẩn đoán, root renice an toàn và rollback\n"
             + "• MGLRU: theo dõi reclaim/no_progress; mặc định OFF\n"
             + "• VM swappiness: 6 chế độ, áp dụng riêng khi bạn xác nhận root\n"
             + "• GPU: driver có chế độ 15/5 nếu topology hỗ trợ; chưa đo thực tế\n"
             + "• VPU: driver được giữ; chưa chạy graph inference\n"
             + "• Nhiệt/pin/mạng/I-O: chỉ đọc chỉ số Android cho phép\n"
             + "• Log và chẩn đoán: phân tích theo quy tắc, xuất báo cáo\n"
             + "• Giọng nói: dùng dịch vụ Android khi có\n\n"
             + "CHƯA CÓ MÔ HÌNH AI / CHƯA XÁC MINH\n"
             + "• Qwen3 thật: có thể dùng sau khi tải model và cài engine ARM64\n"
             + "• GPU+VPU inference hợp nhất / NPU thật (chưa có)\n"
             + "• Offload MGLRU sang GPU/VPU (không hỗ trợ)\n"
             + "• Chứng nhận boot và độ ổn định khi bật MGLRU";
    }

    private void confirmMode(String mode) {
        int chosen = java.util.Arrays.asList("balanced","performance","gaming","battery","stability","research").indexOf(mode);
        if (chosen < 0) return;
        String cmd = "printf '"+chosen+"' > /sys/kernel/alice/mode";
        confirmRoot("Chọn chế độ "+mode,
                cmd);
    }
    private void confirmRoot(String title, String command) {
        new AlertDialog.Builder(this).setTitle(title)
          .setMessage("Thao tác chỉ ghi vào giao diện ALICE của kernel, cần root. MGLRU và xung/điện áp giữ nguyên. Tiếp tục?")
          .setNegativeButton("Hủy", null)
          .setPositiveButton("Đồng ý", (d,which) -> new Thread(() -> {
              int status = -1;
              try {
                  Process p = new ProcessBuilder("su", "-c", command)
                          .redirectErrorStream(true).start();
                  status=p.waitFor();
              } catch (Exception ignored) {}
              final int code = status;
              runOnUiThread(() -> toast(code == 0 ? "Đã gửi cấu hình" :
                      "Không thể thao tác: kiểm tra quyền root hoặc kernel V12R61"));
          }).start()).show();
    }
    private String offline(String question) {
        String q=question.toLowerCase(Locale.ROOT);
        String result;
        if (q.contains("mglru")||q.contains("treo")||q.contains("reclaim"))
            result="MGLRU phải thực hiện trên CPU. Nếu S8+ treo, giữ OFF và kiểm tra pstore / no_progress; không thể offload page table sang GPU/VPU.";
        else if(q.contains("gpu")||q.contains("npu"))
            result="Mali-G71: GPU 15 graphics + 5 compute JS2 chỉ hoạt động nếu topology phù hợp; chưa có NPU vật lý.";
        else if(q.contains("vpu")||q.contains("camera"))
            result="VPU Samsung sử dụng giao diện VS4L/vertex, cần graph/firmware riêng. GPU và VPU không hợp nhất vật lý.";
        else if(q.contains("ram")||q.contains("zram")||q.contains("swap"))
            result="Đo MemAvailable, PSI some/full, swap usage và reclaim no_progress; không ép swappiness khi chưa kiểm chứng.";
        else if(q.contains("pin")||q.contains("nhiệt")||q.contains("heat"))
            result="Giữ xung CPU và thermal từ V12R5T, giảm tải nền nếu thấy nhiệt độ tăng.";
        else result="Mình là ALICE offline theo quy tắc. Hãy hỏi về CPU/GPU/RAM, MGLRU, zRAM, VPU, nhiệt, pin hay crash.";
        return result;
    }
    private void answer(String q) {
        String result=offline(q);
        reply.setText("Bạn: "+q+"\nALICE: "+result);
        if(tts!=null) tts.speak(result,TextToSpeech.QUEUE_FLUSH,null,"alice_answer");
    }

    private void scanProcesses() {
        processesPanel.setText("Đang quét tiến trình qua KernelSU…");
        new Thread(() -> {
            AliceProcessEngine.Snapshot snap = AliceProcessEngine.scan(this);
            lastProcessSnapshot = snap;
            StringBuilder summary = new StringBuilder();
            if (snap.error != null) {
                summary.append("Lỗi root: ").append(snap.error);
            } else {
                summary.append("Số ứng dụng/tiến trình đã nhận diện: ")
                       .append(snap.processes.size()).append("\n");
                int count = 0;
                for (AliceProcessEngine.Entry e : snap.processes) {
                    if (count++ >= 18) break;
                    summary.append(e.eligible() ? "● " : "○ ")
                           .append(e.line()).append("\n");
                }
                summary.append("● = nền đủ điều kiện; ○ = chỉ giám sát.");
            }
            String output = summary.toString();
            runOnUiThread(() -> processesPanel.setText(output));
        }, "alice-manual-process-scan").start();
    }

    private void analyzeProcesses() {
        processesPanel.setText("Qwen3 đang nhận số liệu tiến trình; không cấp quyền chạy lệnh…");
        new Thread(() -> {
            AliceProcessEngine.Snapshot snap = AliceProcessEngine.scan(this);
            lastProcessSnapshot = snap;
            String info = AliceProcessEngine.forModel(snap);
            String telemetry = buildReport() + "\n" + info;
            runOnUiThread(() -> {
                if (snap.error != null) {
                    processesPanel.setText("Không thể quét: " + snap.error);
                    return;
                }
                reply.setText("Đang phân tích tiến trình bằng Qwen3 (không thực thi khuyến nghị)...");
                AliceOfflineModel.infer(this,
                    "Phân tích tiến trình RAM/CPU, cảnh báo app chạy nền bất thường. "
                    + "Ưu tiên ổn định S8+, không đề xuất kill các dịch vụ hệ thống. "
                    + "Chỉ dựa vào số liệu, nêu bất định.",
                    telemetry, msg -> runOnUiThread(() -> reply.setText(msg)));
            });
        }, "alice-process-inference").start();
    }

    private void chooseProcessToLimit() {
        AliceProcessEngine.Snapshot snap = lastProcessSnapshot;
        if (snap == null || snap.error != null || snap.processes.isEmpty()) {
            toast("Quét danh sách tiến trình trước");
            return;
        }
        java.util.ArrayList<AliceProcessEngine.Entry> eligible = new java.util.ArrayList<>();
        for (AliceProcessEngine.Entry e : snap.processes)
            if (e.eligible()) eligible.add(e);
        if (eligible.isEmpty()) { toast("Không có app nền đủ điều kiện"); return; }
        String[] labels = new String[Math.min(eligible.size(), 20)];
        for (int i = 0; i < labels.length; i++) labels[i] = eligible.get(i).line();
        new AlertDialog.Builder(this)
          .setTitle("Chọn app nền cần giảm ưu tiên CPU")
          .setItems(labels, (dialog, index) -> {
              AliceProcessEngine.Entry selected = eligible.get(index);
              new AlertDialog.Builder(this)
                .setTitle("Áp dụng nice +10 cho PID " + selected.pid + "?")
                .setMessage(selected.line()
                    + "\nChỉ thực hiện nếu app vẫn đang cache (oom_adj ≥ 900). "
                    + "Không kill, không thay MGLRU. Có thể khôi phục.")
                .setNegativeButton("Hủy", null)
                .setPositiveButton("Giảm ưu tiên", (d, w) -> new Thread(() -> {
                    String result;
                    try { result = AliceProcessEngine.limit(this, selected); }
                    catch (Exception ex) { result = ex.getMessage(); }
                    String msg=result;
                    runOnUiThread(() -> processesPanel.setText(msg));
                }, "alice-manual-renice").start()).show();
          }).show();
    }

    private void confirmAutoProcess() {
        new AlertDialog.Builder(this)
          .setTitle("Bật ALICE Process AI tự động?")
          .setMessage("ALICE đọc tiến trình mỗi 30 giây. Chỉ khi app bên thứ ba "
            + "đã nằm trong cache, dùng CPU nhiều và RAM trên 96 MB, "
            + "ALICE mới giới hạn nice=+10; tối đa 1 app mỗi 2 phút. "
            + "Không kill ứng dụng, không can thiệp zygote/system_server. "
            + "Có thông báo chạy nền và nút khôi phục.")
          .setNegativeButton("Hủy", null)
          .setPositiveButton("Bật", (d,w) -> {
              Intent intent = new Intent(this, AliceProcessService.class);
              intent.setAction(AliceProcessService.START);
              try {
                  if (android.os.Build.VERSION.SDK_INT >= 26) startForegroundService(intent);
                  else startService(intent);
                  toast("Đã yêu cầu bật ALICE Process AI");
              } catch (Exception e) { toast("Không thể bật giám sát: " + e.getMessage()); }
          }).show();
    }

    private void stopAutoProcess() {
        Intent intent = new Intent(this, AliceProcessService.class);
        try {
            stopService(intent);
            toast("Đã yêu cầu dừng; ALICE sẽ khôi phục nice");
        } catch (Exception e) { toast("Không dừng được: " + e.getMessage()); }
        restoreProcesses();
    }

    private void restoreProcesses() {
        new Thread(() -> {
            String result;
            try { result = AliceProcessEngine.restoreAll(this); }
            catch (Exception e) { result = "Lỗi phục hồi: " + e.getMessage(); }
            String text=result;
            runOnUiThread(() -> processesPanel.setText(text));
        }, "alice-restore-processes").start();
    }

    private void askQwenDialog() {
        EditText input = new EditText(this);
        input.setHint("Hỏi Qwen3 offline về RAM, CPU, GPU, MGLRU…");
        new AlertDialog.Builder(this)
            .setTitle("ALICE Qwen3 offline - chỉ chạy khi hỏi")
            .setView(input)
            .setNegativeButton("Hủy", null)
            .setPositiveButton("Chạy AI", (d, w) -> {
                reply.setText("Qwen3 đang suy luận trên CPU ARM64 (giới hạn 3 luồng)...");
                String telemetry = buildReport();
                AliceOfflineModel.infer(this, input.getText().toString(),
                    telemetry, msg -> runOnUiThread(() -> reply.setText(msg)));
            }).show();
    }

    private void askDialog() {
        EditText input=new EditText(this);
        input.setHint("Hỏi Alice về RAM, GPU, MGLRU…");
        new AlertDialog.Builder(this).setTitle("Hỏi ALICE offline")
            .setView(input).setNegativeButton("Hủy",null)
            .setPositiveButton("Gửi",(d,w)->answer(input.getText().toString())).show();
    }
    private void speech() {
        Intent i=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE,"vi-VN");
        i.putExtra(RecognizerIntent.EXTRA_PROMPT,"Bạn muốn hỏi ALICE điều gì?");
        try { startActivityForResult(i,SPEECH_REQUEST); }
        catch(Exception e) {toast("Chưa có dịch vụ nhận dạng giọng nói");}
    }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request==SPEECH_REQUEST && result==RESULT_OK && data!=null) {
            ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if(words!=null && !words.isEmpty()) answer(words.get(0));
        }
    }
    @Override public void onInit(int status) {
        if(tts!=null && status==TextToSpeech.SUCCESS) tts.setLanguage(new Locale("vi","VN"));
    }
    private void toast(String s) { Toast.makeText(this,s,Toast.LENGTH_LONG).show(); }
    @Override protected void onResume() { super.onResume();active=true;handler.post(poll); }
    @Override protected void onPause() { active=false;handler.removeCallbacks(poll);super.onPause(); }
    @Override protected void onDestroy() { if(tts!=null){tts.stop();tts.shutdown();}super.onDestroy(); }
}
