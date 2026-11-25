package tech.airdrop4e;
// Java binding matching the upstream MIT JNI ABI.
public final class A4eCore {
 public static final A4eCore INSTANCE=new A4eCore();
 static { System.loadLibrary("airdrop_ffi"); }
 private A4eCore(){}
 public interface PeerCallback { void onPeer(A4ePeer peer); }
 public native void identityLoadOrCreate(String keysDir,String computerName) throws A4eException;
 public native void browse(int timeoutMs,PeerCallback cb) throws A4eException;
 public native void sendFiles(String[] paths,String endpoint,A4eSendOpts opts) throws A4eException;
}