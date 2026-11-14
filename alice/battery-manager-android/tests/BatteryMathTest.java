import com.halot455.alice.battery.BatteryMath;

public final class BatteryMathTest {
    private static void expect(boolean yes, String name) {
        if (!yes) throw new AssertionError(name);
    }
    public static void main(String[] args) {
        expect(BatteryMath.virtualPercent(100)==100,"100");
        expect(BatteryMath.virtualPercent(80)==75,"80");
        expect(BatteryMath.virtualPercent(60)==50,"60");
        expect(BatteryMath.virtualPercent(40)==25,"40");
        expect(BatteryMath.virtualPercent(25)==6,"25");
        expect(BatteryMath.virtualPercent(24)==5,"24");
        BatteryMath.State s=BatteryMath.advance(24,false,false,false);
        expect(s.emergency && s.displayed==24,"24 real emergency, not 25");
        s=BatteryMath.advance(50,true,s.emergency,s.fullSeen);
        expect(s.emergency,"no early release");
        s=BatteryMath.advance(100,true,s.emergency,s.fullSeen);
        expect(s.emergency && s.fullSeen,"stay locked while fully plugged");
        s=BatteryMath.advance(99,false,s.emergency,s.fullSeen);
        expect(!s.emergency && s.normal==99 && s.displayed==99,"unplug releases latch");
        expect(BatteryMath.advance(23,false,true,false).emergency,"reserve persists");
        System.out.println("PASS: S8+ 80/20 actual 24% transition, 100% full-then-unplug latch");
    }
}
