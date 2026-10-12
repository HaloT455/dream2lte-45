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
    private TextView dashboard, reply;
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
        root.addView(text("ALICE  •  System Intelligence", 24, true));
        root.addView(text("Exynos 8895  |  V12R60 Kernel Bridge", 13, false));
        dashboard = text("Reading telemetry…", 14, false);
        dashboard.setTextIsSelectable(true);
        root.addView(dashboard);
        button(root, "Làm mới thông số", v -> dashboard.setText(buildReport()));
        root.addView(text("Chế độ hệ thống (cần module KernelSU)", 18, true));
        final String[] modes = {"balanced","performance","gaming","battery","stability","research"};
        for (String mode : modes) button(root, "Chọn " + mode, v -> confirmMode(mode));
        button(root, "Tắt chính sách ghi hệ thống", v -> confirmRoot("Tắt policy và khôi phục",
                "printf 0 > /data/adb/alice/state/policy_enabled"));
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
    private String buildReport() {
        boolean bridge = new File("/sys/kernel/alice/version").exists();
        StringBuilder s=new StringBuilder();
        s.append("ALICE kernel bridge: ").append(bridge?"Phát hiện":"Chưa có hoặc bị chặn").append('\n');
        if (bridge) {
            s.append(read("/sys/kernel/alice/version",150)).append('\n');
            s.append("Reclaim: ").append(read("/sys/kernel/alice/mm_reclaim",700)).append('\n');
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
    private void confirmMode(String mode) {
        String cmd = "mkdir -p /data/adb/alice/state; printf '"+mode+
                "' > /data/adb/alice/state/mode";
        confirmRoot("Chọn chế độ "+mode,
                cmd);
    }
    private void confirmRoot(String title, String command) {
        new AlertDialog.Builder(this).setTitle(title)
          .setMessage("Thao tác cần quyền root KernelSU. Không bật MGLRU hay đổi xung/điện áp. Tiếp tục?")
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
                      "Không thể thao tác root / chưa cài module ALICE"));
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
