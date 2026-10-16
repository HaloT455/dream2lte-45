// SPDX-License-Identifier: Apache-2.0
#include "Controller.h"
#include <aidl/android/hardware/power/BnPower.h>
#include <aidl/android/hardware/power/BnPowerHintSession.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <android/log.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <memory>
#include <mutex>
#include <string>
#include <time.h>
#include <unistd.h>
#include <vector>

using namespace aidl::android::hardware::power;
using ndk::ScopedAStatus;
static constexpr char NODE[] = "/sys/power/alice_power_hint";
static constexpr int SLOTS = 16;

static ScopedAStatus error(int code) { return ScopedAStatus::fromExceptionCode(code); }
static bool systemCaller() {
    uid_t uid = AIBinder_getCallingUid();
    return uid == 1000 || uid == 0;
}
static int64_t monotonicNs() {
    timespec t{};
    clock_gettime(CLOCK_MONOTONIC, &t);
    return int64_t(t.tv_sec) * 1000000000 + t.tv_nsec;
}

class Backend {
    std::mutex lock;
    std::array<bool, SLOTS> used{};
    std::atomic<bool> ready{false};
    bool warned = false;
    uint64_t created = 0, reports = 0;
public:
    bool write(const std::string& command) {
        int fd = open(NODE, O_WRONLY | O_CLOEXEC);
        ssize_t n = fd < 0 ? -1 : ::write(fd, command.data(), command.size());
        int saved = errno;
        if (fd >= 0) close(fd);
        if (n != static_cast<ssize_t>(command.size())) {
            ready.store(false);
            std::lock_guard<std::mutex> guard(lock);
            if (!warned) {
                __android_log_print(ANDROID_LOG_ERROR, "AlicePower", "hint backend unavailable: %s", strerror(saved));
                warned = true;
            }
            return false;
        }
        return true;
    }
    void init() { ready = write("reset\n"); }
    bool available() const { return ready.load(); }
    int acquire() {
        std::lock_guard<std::mutex> guard(lock);
        for (int i = 0; i < SLOTS; i++) if (!used[i]) { used[i] = true; created++; return i; }
        return -1;
    }
    void clear(int slot) { write("session " + std::to_string(slot) + " 0 0\n"); }
    void release(int slot) {
        // Clear before making the slot available to a new session.
        clear(slot);
        std::lock_guard<std::mutex> guard(lock);
        used[slot] = false;
    }
    void report(int slot, int level, int ms) {
        if (write("session " + std::to_string(slot) + " " + std::to_string(level) + " " + std::to_string(ms) + "\n")) {
            std::lock_guard<std::mutex> guard(lock);
            reports++;
        }
    }
    void dump(int fd) {
        std::lock_guard<std::mutex> guard(lock);
        int active = 0;
        for (bool occupied : used) active += occupied;
        dprintf(fd, "session_active=%d session_created=%llu report_batches=%llu\n", active,
                static_cast<unsigned long long>(created), static_cast<unsigned long long>(reports));
    }
};

class Session final : public BnPowerHintSession {
    std::shared_ptr<Backend> backend;
    std::mutex lock;
    DeadlineController controller;
    int slot;
    uid_t owner;
    bool paused = false;
    bool closed = false;
    bool authorized() const { return systemCaller() || AIBinder_getCallingUid() == owner; }
    void closeLocked() {
        if (!closed) {
            backend->release(slot);
            closed = true;
            controller.reset();
        }
    }
public:
    Session(std::shared_ptr<Backend> b, int s, uid_t uid, int64_t target)
        : backend(std::move(b)), controller(target), slot(s), owner(uid) {}
    ~Session() override {
        std::lock_guard<std::mutex> guard(lock);
        closeLocked();
    }
    ScopedAStatus updateTargetWorkDuration(int64_t target) override {
        if (!authorized()) return error(EX_SECURITY);
        if (!DeadlineController::validTarget(target)) return error(EX_ILLEGAL_ARGUMENT);
        std::lock_guard<std::mutex> guard(lock);
        if (closed) return error(EX_ILLEGAL_STATE);
        controller.target = target;
        controller.reset();
        backend->clear(slot);
        return ScopedAStatus::ok();
    }
    ScopedAStatus reportActualWorkDuration(const std::vector<WorkDuration>& durations) override {
        if (!authorized()) return error(EX_SECURITY);
        if (durations.empty() || durations.size() > 64) return error(EX_ILLEGAL_ARGUMENT);
        std::lock_guard<std::mutex> guard(lock);
        if (closed) return error(EX_ILLEGAL_STATE);
        if (paused) return ScopedAStatus::ok();
        // Validate the complete batch before changing controller state.
        auto next = controller;
        int64_t now = monotonicNs();
        for (const auto& d : durations)
            if (!next.sample(d.timeStampNanos, d.durationNanos, now)) return error(EX_ILLEGAL_ARGUMENT);
        controller = next;
        backend->report(slot, controller.level, controller.leaseMs());
        return ScopedAStatus::ok();
    }
    ScopedAStatus pause() override {
        if (!authorized()) return error(EX_SECURITY);
        std::lock_guard<std::mutex> guard(lock);
        if (closed) return error(EX_ILLEGAL_STATE);
        paused = true;
        controller.reset();
        backend->clear(slot);
        return ScopedAStatus::ok();
    }
    ScopedAStatus resume() override {
        if (!authorized()) return error(EX_SECURITY);
        std::lock_guard<std::mutex> guard(lock);
        if (closed) return error(EX_ILLEGAL_STATE);
        paused = false;
        controller.reset();
        backend->clear(slot);
        return ScopedAStatus::ok();
    }
    ScopedAStatus close() override {
        if (!authorized()) return error(EX_SECURITY);
        std::lock_guard<std::mutex> guard(lock);
        closeLocked();
        return ScopedAStatus::ok();
    }
};

class Power final : public BnPower {
    std::shared_ptr<Backend> backend = std::make_shared<Backend>();
    static bool modeSupported(Mode mode) {
        switch (mode) {
            case Mode::LOW_POWER: case Mode::LAUNCH: case Mode::INTERACTIVE:
            case Mode::DEVICE_IDLE: case Mode::DISPLAY_INACTIVE: return true;
            default: return false;
        }
    }
    static bool boostSupported(Boost boost) {
        return boost == Boost::INTERACTION || boost == Boost::DISPLAY_UPDATE_IMMINENT;
    }
public:
    Power() { backend->init(); }
    ScopedAStatus setMode(Mode mode, bool enabled) override {
        if (!systemCaller()) return error(EX_SECURITY);
        if (!backend->available() || !modeSupported(mode)) return error(EX_UNSUPPORTED_OPERATION);
        backend->write("mode " + std::to_string(static_cast<int>(mode)) + " " + (enabled ? "1\n" : "0\n"));
        return ScopedAStatus::ok();
    }
    ScopedAStatus isModeSupported(Mode mode, bool* supported) override {
        *supported = backend->available() && modeSupported(mode);
        return ScopedAStatus::ok();
    }
    ScopedAStatus setBoost(Boost boost, int32_t durationMs) override {
        if (!systemCaller()) return error(EX_SECURITY);
        if (!backend->available() || !boostSupported(boost)) return error(EX_UNSUPPORTED_OPERATION);
        // A negative duration cancels, zero uses a short default, positive is capped.
        int ms = durationMs < 0 ? 0 : (durationMs == 0 ? 80 : std::min(durationMs, 250));
        backend->write("boost " + std::to_string(static_cast<int>(boost)) + " " + std::to_string(ms) + "\n");
        return ScopedAStatus::ok();
    }
    ScopedAStatus isBoostSupported(Boost boost, bool* supported) override {
        *supported = backend->available() && boostSupported(boost);
        return ScopedAStatus::ok();
    }
    ScopedAStatus createHintSession(int32_t tgid, int32_t uid, const std::vector<int32_t>& threads,
                                  int64_t target, std::shared_ptr<IPowerHintSession>* session) override {
        *session = nullptr;
        // PowerHintManagerService owns UID/TGID/thread-membership validation.
        // Only the trusted framework may create sessions; no arbitrary affinity is set here.
        if (!systemCaller()) return error(EX_SECURITY);
        if (!backend->available()) return error(EX_UNSUPPORTED_OPERATION);
        if (tgid <= 0 || uid < 0 || threads.empty() || threads.size() > 64 ||
            !DeadlineController::validTarget(target)) return error(EX_ILLEGAL_ARGUMENT);
        for (int tid : threads) if (tid <= 0) return error(EX_ILLEGAL_ARGUMENT);
        int slot = backend->acquire();
        if (slot < 0) return error(EX_ILLEGAL_STATE);
        *session = ndk::SharedRefBase::make<Session>(backend, slot, uid, target);
        return ScopedAStatus::ok();
    }
    ScopedAStatus getHintSessionPreferredRate(int64_t* rate) override {
        if (!backend->available()) return error(EX_UNSUPPORTED_OPERATION);
        *rate = 16666667;
        return ScopedAStatus::ok();
    }
    binder_status_t dump(int fd, const char**, uint32_t) override {
        if (!systemCaller() && AIBinder_getCallingUid() != 2000) return STATUS_PERMISSION_DENIED;
        dprintf(fd, "ALICE Power HAL R16 AIDL V2; backend=%s; sessions=%d\n",
                backend->available() ? "ready" : "unavailable", SLOTS);
        backend->dump(fd);
        char buf[512];
        int input = open(NODE, O_RDONLY | O_CLOEXEC);
        if (input >= 0) {
            ssize_t n = read(input, buf, sizeof(buf));
            if (n > 0) (void)::write(fd, buf, n);
            ::close(input);
        }
        return STATUS_OK;
    }
};

int main() {
    ABinderProcess_setThreadPoolMaxThreadCount(2);
    auto power = ndk::SharedRefBase::make<Power>();
    const std::string name = std::string(IPower::descriptor) + "/default";
    binder_status_t status = AServiceManager_addService(power->asBinder().get(), name.c_str());
    if (status != STATUS_OK) {
        __android_log_print(ANDROID_LOG_ERROR, "AlicePower", "registration failed: %d", status);
        return 1;
    }
    __android_log_write(ANDROID_LOG_INFO, "AlicePower", "R16 AIDL V2 EnergyStep hint service registered");
    ABinderProcess_joinThreadPool();
    return 1;
}
