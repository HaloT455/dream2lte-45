package com.halo.mglrudiag;

import android.content.Context;
import android.opengl.EGL14;
import android.opengl.EGLConfig;
import android.opengl.EGLContext;
import android.opengl.EGLDisplay;
import android.opengl.EGLExt;
import android.opengl.EGLSurface;
import android.os.Process;
import android.os.SystemClock;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.Buffer;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Locale;
import java.util.Random;

import static android.opengl.GLES31.*;

final class HaloCompressionProbe {
    private static final int PAGE_SIZE = 4096;
    private static final int PAGES = 64;
    private static final int BYTES = PAGES * PAGE_SIZE;
    private static final long WAIT_NS = 2_000_000_000L;

    private HaloCompressionProbe() {}

    static synchronized String run(Context context) throws IOException {
        byte[][] pages = samplePages();
        ByteBuffer input = ByteBuffer.allocateDirect(BYTES);
        for (byte[] page : pages)
            input.put(page);
        input.flip();
        String source;
        try (InputStream shader = context.getAssets().open("lz4kd_pages.comp")) {
            ByteArrayOutputStream sourceBytes = new ByteArrayOutputStream();
            byte[] bytes = new byte[4096];
            int read;
            while ((read = shader.read(bytes)) != -1)
                sourceBytes.write(bytes, 0, read);
            source = new String(sourceBytes.toByteArray(), StandardCharsets.UTF_8);
        }

        // Load the JNI codec before timing CPU compression.
        compressOnCpu(pages[0]);
        int cpuBytes = 0;
        long cpuStart = SystemClock.elapsedRealtimeNanos();
        for (byte[] page : pages)
            cpuBytes += compressOnCpu(page).length;
        double cpuMs = elapsedMs(cpuStart);

        try (ProbeContext egl = new ProbeContext()) {
            egl.initialize();
            String renderer = glGetString(GL_RENDERER);
            if (renderer == null || !renderer.contains("Mali"))
                throw new IOException("Cần GPU Mali. Renderer: " + renderer);

            int program = compile(source);
            glUseProgram(program);
            int[] buffers = new int[3];
            glGenBuffers(buffers.length, buffers, 0);
            long gpuStart = SystemClock.elapsedRealtimeNanos();
            storage(buffers[0], 0, BYTES, input, GL_STREAM_DRAW);
            storage(buffers[1], 1, BYTES, null, GL_STREAM_READ);
            storage(buffers[2], 2, PAGES * Integer.BYTES, null, GL_STREAM_READ);
            checkGl("Chuẩn bị bộ đệm");
            awaitCompute();
            double gpuMs = elapsedMs(gpuStart);

            SlotSample after;
            long jobs;
            try (SlotProbe slot = new SlotProbe()) {
                SlotSample before = slot.read();
                gpuStart = SystemClock.elapsedRealtimeNanos();
                glDispatchCompute(PAGES, 1, 1);
                glMemoryBarrier(GL_BUFFER_UPDATE_BARRIER_BIT);
                checkGl("Gửi job nén");
                awaitCompute();
                gpuMs += elapsedMs(gpuStart);
                after = slot.read();
                jobs = after.verifyDispatch(before);
            }

            gpuStart = SystemClock.elapsedRealtimeNanos();
            ByteBuffer lengths = download(buffers[2], PAGES * Integer.BYTES);
            ByteBuffer output = download(buffers[1], BYTES);
            gpuMs += elapsedMs(gpuStart);
            glDeleteBuffers(buffers.length, buffers, 0);
            glDeleteProgram(program);

            int gpuPages = 0;
            int hybridBytes = 0;
            double fallbackMs = 0;
            for (int i = 0; i < PAGES; i++) {
                int size = lengths.getInt(i * Integer.BYTES);
                if ((size == 0) != (i % 4 == 0))
                    throw new IOException("GPU trả sai trạng thái nén ở trang " + i);
                byte[] frame;
                if (size == 0) {
                    long start = SystemClock.elapsedRealtimeNanos();
                    frame = compressOnCpu(pages[i]);
                    fallbackMs += elapsedMs(start);
                } else {
                    if (size < 0 || size >= PAGE_SIZE)
                        throw new IOException("Kích thước frame GPU sai ở trang " + i);
                    frame = new byte[size];
                    output.position(i * PAGE_SIZE);
                    output.get(frame);
                    gpuPages++;
                }
                if (!Arrays.equals(pages[i], HaloLz4kd.decompress(frame)))
                    throw new IOException("Giải nén sai ở trang " + i);
                hybridBytes += frame.length;
            }

            return String.format(Locale.ROOT,
                    "%s\nLZ4KD · JS2 · %d job · %d/5 shader trong affinity (0x%x)"
                    + "\n\nGiải nén khớp %d/%d trang 4 KiB\nGPU nén %d trang · CPU dự phòng %d trang"
                    + "\nGPU gồm tải và đọc %.2f ms · CPU dự phòng %.2f ms · CPU toàn bộ %.2f ms"
                    + "\nGPU + CPU %d byte · CPU toàn bộ %d byte",
                    renderer, jobs, Long.bitCount(after.affinity), after.affinity,
                    PAGES, PAGES, gpuPages, PAGES - gpuPages,
                    gpuMs, fallbackMs, cpuMs, hybridBytes, cpuBytes);
        }
    }

    private static byte[] compressOnCpu(byte[] page) throws IOException {
        byte[] block = HaloLz4kd.compress(page);
        if (block == null)
            throw new IOException("CPU không nén được trang LZ4KD mẫu.");
        return block;
    }

    private static byte[][] samplePages() {
        byte[][] pages = new byte[PAGES][PAGE_SIZE];
        Random random = new Random(8895);
        for (int i = 0; i < pages.length; i++) {
            byte[] page = pages[i];
            random.nextBytes(page);
            switch (i % 4) {
                case 0:
                    break;
                case 1:
                    Arrays.fill(page, 0, 4032, (byte) i);
                    break;
                case 2:
                    Arrays.fill(page, 0, 2048, (byte) 0);
                    Arrays.fill(page, 3072, PAGE_SIZE, (byte) i);
                    break;
                case 3:
                    Arrays.fill(page, 2048, PAGE_SIZE, (byte) i);
                    break;
            }
        }
        return pages;
    }

    private static double elapsedMs(long start) {
        return (SystemClock.elapsedRealtimeNanos() - start) / 1_000_000.0;
    }

    private static int compile(String source) throws IOException {
        int shader = glCreateShader(GL_COMPUTE_SHADER);
        glShaderSource(shader, source);
        glCompileShader(shader);
        int[] status = new int[1];
        glGetShaderiv(shader, GL_COMPILE_STATUS, status, 0);
        if (status[0] == 0)
            throw new IOException(glGetShaderInfoLog(shader));
        int program = glCreateProgram();
        glAttachShader(program, shader);
        glLinkProgram(program);
        glDeleteShader(shader);
        glGetProgramiv(program, GL_LINK_STATUS, status, 0);
        if (status[0] == 0)
            throw new IOException(glGetProgramInfoLog(program));
        return program;
    }

    private static void storage(int buffer, int index, int bytes, Buffer data, int usage) {
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, buffer);
        glBufferData(GL_SHADER_STORAGE_BUFFER, bytes, data, usage);
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, index, buffer);
    }

    private static void awaitCompute() throws IOException {
        long fence = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE, 0);
        if (fence == 0)
            throw new IOException("Không tạo được GPU fence");
        int result = glClientWaitSync(fence, GL_SYNC_FLUSH_COMMANDS_BIT, WAIT_NS);
        glDeleteSync(fence);
        if (result != GL_ALREADY_SIGNALED && result != GL_CONDITION_SATISFIED)
            throw new IOException("GPU chưa hoàn tất job nén (" + result + ")");
    }

    private static ByteBuffer download(int buffer, int bytes) throws IOException {
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, buffer);
        Buffer mapping = glMapBufferRange(GL_SHADER_STORAGE_BUFFER, 0, bytes, GL_MAP_READ_BIT);
        if (!(mapping instanceof ByteBuffer))
            throw new IOException("Không đọc được bộ đệm GPU");
        ByteBuffer copy = ByteBuffer.allocate(bytes).order(ByteOrder.LITTLE_ENDIAN);
        copy.put((ByteBuffer) mapping);
        if (!glUnmapBuffer(GL_SHADER_STORAGE_BUFFER))
            throw new IOException("Bộ đệm GPU bị mất");
        copy.flip();
        return copy;
    }

    private static void checkGl(String action) throws IOException {
        int error = glGetError();
        if (error != GL_NO_ERROR)
            throw new IOException(action + " · GL 0x" + Integer.toHexString(error));
    }

    private static final class SlotSample {
        final long generation;
        final long js2;
        final long other;
        final long affinity;
        final long reserved;

        SlotSample(String[] fields, long reserved) {
            generation = Long.parseUnsignedLong(fields[1]);
            js2 = Long.parseUnsignedLong(fields[2]);
            other = Long.parseUnsignedLong(fields[3]);
            affinity = Long.parseUnsignedLong(fields[4].substring(2), 16);
            this.reserved = reserved;
        }

        long verifyDispatch(SlotSample before) throws IOException {
            if (generation != before.generation || reserved != before.reserved)
                throw new IOException("Phiên HALO hoặc phân vùng shader đã đổi giữa bài thử.");
            long jobs = js2 - before.js2;
            long otherJobs = other - before.other;
            if (jobs <= 0 || otherJobs != 0 || Long.bitCount(reserved) != 5
                    || affinity == 0 || (affinity & ~reserved) != 0) {
                throw new IOException(String.format(Locale.ROOT,
                        "Chưa xác nhận được JS2 · job JS2=%d · compute khác=%d"
                        + " · affinity=0x%x · phân vùng=0x%x",
                        jobs, otherJobs, affinity, reserved));
            }
            return jobs;
        }
    }

    private static final class SlotProbe implements AutoCloseable {
        private static final String NODE = HardwareStatus.MALI + "/halo_probe";
        private final int pid = Process.myPid();

        SlotProbe() throws IOException {
            RootUtil.Result result = RootUtil.execRoot("echo " + pid + " > " + NODE);
            if (result.code != 0)
                throw new IOException("Không bật được HALO JS2. Kiểm tra boot thử và quyền KernelSU.\n"
                        + result.output.trim());
        }

        SlotSample read() throws IOException {
            RootUtil.Result result = RootUtil.execRoot("cat " + NODE + " " + HardwareStatus.MALI + "/core_mask");
            String[] lines = result.output.trim().split("\n", 2);
            String[] fields = lines[0].trim().split("\\s+");
            if (result.code != 0 || lines.length != 2 || fields.length != 5
                    || !fields[0].equals(Integer.toString(pid)) || !fields[4].startsWith("0x"))
                throw new IOException("Không đọc được bộ đếm JS2.\n" + result.output.trim());
            return new SlotSample(fields, HardwareStatus.mask(lines[1], "Current core mask (JS2)"));
        }

        @Override
        public void close() {
            RootUtil.execRoot("read -r owner stats < " + NODE
                    + " && [ \"$owner\" = " + pid + " ] && echo 0 > " + NODE);
        }
    }

    // The probe activity owns its process and EGL display.
    private static final class ProbeContext implements AutoCloseable {
        private EGLDisplay display = EGL14.EGL_NO_DISPLAY;
        private EGLContext context = EGL14.EGL_NO_CONTEXT;
        private EGLSurface surface = EGL14.EGL_NO_SURFACE;

        void initialize() throws IOException {
            display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);
            int[] version = new int[2];
            if (display == EGL14.EGL_NO_DISPLAY
                    || !EGL14.eglInitialize(display, version, 0, version, 1))
                throw new IOException("Không khởi tạo được EGL");
            int[] configAttrs = {
                    EGL14.EGL_SURFACE_TYPE, EGL14.EGL_PBUFFER_BIT,
                    EGL14.EGL_RENDERABLE_TYPE, EGLExt.EGL_OPENGL_ES3_BIT_KHR,
                    EGL14.EGL_NONE
            };
            EGLConfig[] configs = new EGLConfig[1];
            int[] count = new int[1];
            if (!EGL14.eglChooseConfig(display, configAttrs, 0, configs, 0, 1, count, 0)
                    || count[0] == 0)
                throw new IOException("Thiếu cấu hình OpenGL ES 3");
            int[] contextAttrs = {EGL14.EGL_CONTEXT_CLIENT_VERSION, 3, EGL14.EGL_NONE};
            int[] surfaceAttrs = {EGL14.EGL_WIDTH, 1, EGL14.EGL_HEIGHT, 1, EGL14.EGL_NONE};
            context = EGL14.eglCreateContext(display, configs[0], EGL14.EGL_NO_CONTEXT,
                    contextAttrs, 0);
            surface = EGL14.eglCreatePbufferSurface(display, configs[0], surfaceAttrs, 0);
            if (context == EGL14.EGL_NO_CONTEXT || surface == EGL14.EGL_NO_SURFACE
                    || !EGL14.eglMakeCurrent(display, surface, surface, context))
                throw new IOException("Không mở được context compute của Mali");
        }

        @Override
        public void close() {
            if (display == EGL14.EGL_NO_DISPLAY)
                return;
            EGL14.eglMakeCurrent(display, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE,
                    EGL14.EGL_NO_CONTEXT);
            if (surface != EGL14.EGL_NO_SURFACE)
                EGL14.eglDestroySurface(display, surface);
            if (context != EGL14.EGL_NO_CONTEXT)
                EGL14.eglDestroyContext(display, context);
            EGL14.eglTerminate(display);
            EGL14.eglReleaseThread();
        }
    }
}
