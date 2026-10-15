// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <algorithm>
#include <cstdint>

// A small deadline controller. It only requests short, bounded frequency floors;
// it does not change affinity, task priorities, thermal caps or native DVFS limits.
struct DeadlineController {
    int level = 0;
    int64_t target;
    int64_t lastTimestamp = 0;
    int64_t ratio = 1000;
    explicit DeadlineController(int64_t ns) : target(ns) {}
    static bool validTarget(int64_t ns) { return ns >= 1000000 && ns <= 1000000000; }
    void reset() { level = 0; ratio = 1000; lastTimestamp = 0; }
    bool sample(int64_t timestamp, int64_t duration, int64_t now) {
        if (timestamp <= lastTimestamp || timestamp > now || now - timestamp > 1000000000 ||
            duration <= 0 || duration > 1000000000) return false;
        lastTimestamp = timestamp;
        ratio = (ratio * 3 + duration * 1000 / target) / 4;
        if (ratio > 1050) level = std::min(level + 1, 3);
        else if (ratio < 900) level = std::max(level - 1, 0);
        return true;
    }
    int leaseMs() const {
        return static_cast<int>(std::clamp(target * 4 / 1000000, int64_t(40), int64_t(250)));
    }
};
