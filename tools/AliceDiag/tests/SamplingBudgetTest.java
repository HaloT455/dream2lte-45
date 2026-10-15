package com.halot455.alice.diag;

public class SamplingBudgetTest {
    static void check(boolean pass, String message) { if (!pass) throw new AssertionError(message); }
    public static void main(String[] args) {
        SamplingBudget lag = new SamplingBudget(15_000);
        check(lag.observe(20) == 15_000, "Cheap sample keeps 15s post-collection rest");
        check(lag.observe(750) == 30_000, "750ms collection backs off");
        check(lag.observe(1) == 30_000, "No faster catch-up after backoff");
        check(lag.observe(2000) == 60_000, "2s collection backs off to 60s");
        check(lag.observe(7400) == 60_000, "Legacy slow sample cannot cause a busy loop");
        SamplingBudget battery = new SamplingBudget(60_000);
        check(battery.observe(750) == 60_000, "Battery mode never speeds up");
        System.out.println("SamplingBudget: post-collection rest, monotonic backoff and slow-sample checks passed");
    }
}
