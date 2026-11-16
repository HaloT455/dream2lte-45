package de.robv.android.xposed;
import java.lang.reflect.Member;
public final class XposedBridge {
    private XposedBridge() {}
    public static XC_MethodHook.Unhook hookMethod(Member m, XC_MethodHook h) {
        throw new UnsupportedOperationException("Compile-time stub only");
    }
    public static void log(String msg) {}
}
