package com.halot455.alice.battery;

/** Pure 80/20 state machine: real fuel-gauge percent must never be overwritten. */
public final class BatteryMath {
    private BatteryMath() {}
    public static int clamp(int n) { return Math.max(0, Math.min(100, n)); }
    public static int virtualPercent(int real) {
        return Math.min(100, Math.max(0, (Math.max(clamp(real) - 20, 0) * 100 + 40) / 80));
    }

    public static final class State {
        public final boolean emergency;
        public final boolean fullSeen;
        public final int real;
        public final int normal;
        public final int displayed;
        public State(boolean emergency, boolean fullSeen, int real, int normal) {
            this.emergency = emergency;
            this.fullSeen = fullSeen;
            this.real = real;
            this.normal = normal;
            this.displayed = emergency ? real : normal;
        }
    }

    public static State advance(int percent, boolean plugged, boolean previousEmergency,
                                boolean previousFullSeen) {
        int real = clamp(percent);
        int normal = virtualPercent(real);
        boolean emergency = previousEmergency;
        boolean fullSeen = previousFullSeen;
        if (emergency) {
            if (plugged && real >= 100) fullSeen = true;
            if (fullSeen && !plugged) {
                emergency = false;
                fullSeen = false;
            }
        } else if (!plugged && normal <= 5) {
            emergency = true;
            fullSeen = false;
        }
        if (!emergency) fullSeen = false;
        return new State(emergency, fullSeen, real, normal);
    }
}
