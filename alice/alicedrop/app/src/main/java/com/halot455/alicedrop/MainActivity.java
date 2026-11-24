package com.halot455.alicedrop;
import android.app.Activity;
import android.os.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.net.*;
import android.net.nsd.*;
import android.net.wifi.aware.WifiAwareManager;
import android.widget.*;
import android.view.*;
import java.io.*;
import java.net.*;
import java.security.SecureRandom;
import java.util.concurrent.*;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
 private TextView status, link, selectedText;
 private Uri selected;
 private File received;
 private volatile ServerSocket server;
 private volatile Socket active;
 private final ExecutorService worker=Executors.newSingleThreadExecutor();
 private final Handler ui=new Handler(Looper.getMainLooper());
 private NsdManager nsd;
 private NsdManager.DiscoveryListener listener;
 private String token;
 private int generation;
 private static final long LIMIT=100L*1024*1024;
 private static final int PICK=1,SAVE=2;
 @Override public void onCreate(Bundle b){
  super.onCreate(b);
  LinearLayout layout=new LinearLayout(this); layout.setOrientation(1); layout.setPadding(32,64,32,32);
  ScrollView scroll=new ScrollView(this); scroll.addView(layout); setContentView(scroll);
  TextView title=new TextView(this); title.setText("AliceDrop");title.setTextSize(32); layout.addView(title);
  status=new TextView(this);layout.addView(status);
  selectedText=new TextView(this);layout.addView(selectedText);
  add(layout,"Kiểm tra AirDrop / Wi-Fi Aware",v->probe());
  add(layout,"Dò dịch vụ AirDrop trên mạng hiện tại (10 giây)",v->discover());
  add(layout,"Chọn file",v->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,PICK);});
  add(layout,"Gửi qua bảng chia sẻ Android / Quick Share",v->share());
  add(layout,"Bật truyền Wi-Fi qua Safari (không phải AirDrop)",v->startLan());
  link=new TextView(this);link.setTextIsSelectable(true);layout.addView(link);
  add(layout,"Dừng truyền Wi-Fi",v->stopLan());
  add(layout,"Lưu file đã nhận",v->{if(received==null){msg("Chưa có file nhận");return;} Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/octet-stream").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"AliceDrop-received.bin");startActivityForResult(i,SAVE);});
  if(Intent.ACTION_SEND.equals(getIntent().getAction())){selected=getIntent().getParcelableExtra(Intent.EXTRA_STREAM); updateSelected();}
  probe();
 }
 private void add(LinearLayout l,String label,View.OnClickListener action){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setOnClickListener(action);l.addView(b);}
 private void msg(String s){status.setText(s);}
 private void probe(){
  boolean feature=getPackageManager().hasSystemFeature(PackageManager.FEATURE_WIFI_AWARE);
  WifiAwareManager a=getSystemService(WifiAwareManager.class);
  boolean available=false; try{available=a!=null&&a.isAvailable();}catch(Exception ignored){}
  boolean awdl=false;try{awdl=NetworkInterface.getByName("awdl0")!=null;}catch(Exception ignored){}
  msg("Kernel: "+System.getProperty("os.version")+"\nWi-Fi Aware: "+feature+" / sẵn sàng: "+available+"\nawdl0: "+awdl+"\nAirDrop gốc: chưa xác minh giao tiếp hai chiều. Quick Share phụ thuộc thiết bị và ROM.");
 }
 private void discover(){
  stopDiscovery(); nsd=getSystemService(NsdManager.class); if(nsd==null){msg("NSD không khả dụng");return;}
  listener=new NsdManager.DiscoveryListener(){
   public void onDiscoveryStarted(String s){ui.post(()->msg("Đang dò _airdrop._tcp trên mạng hiện tại…"));}
   public void onDiscoveryStopped(String s){}
   public void onServiceFound(NsdServiceInfo s){ui.post(()->msg("Thấy dịch vụ "+s.getServiceName()+"; chưa xác minh AirDrop/AWDL hoặc truyền file."));}
   public void onServiceLost(NsdServiceInfo s){}
   public void onStartDiscoveryFailed(String s,int e){ui.post(()->msg("Dò thất bại: "+e));}
   public void onStopDiscoveryFailed(String s,int e){}
  };
  try{nsd.discoverServices("_airdrop._tcp.",NsdManager.PROTOCOL_DNS_SD,listener);NsdManager.DiscoveryListener current=listener;ui.postDelayed(()->{if(listener==current)stopDiscovery();},10000);}catch(Exception e){msg("Không thể dò: "+e.getMessage());}
 }
 private void stopDiscovery(){if(listener!=null&&nsd!=null){try{nsd.stopServiceDiscovery(listener);}catch(Exception ignored){}listener=null;}}
 private void updateSelected(){selectedText.setText(selected==null?"Chưa chọn file":"Đã chọn một file");}
 private void share(){if(selected==null){msg("Chọn file trước");return;}String type=getContentResolver().getType(selected);Intent i=new Intent(Intent.ACTION_SEND).setType(type==null?"application/octet-stream":type).putExtra(Intent.EXTRA_STREAM,selected).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);i.setClipData(ClipData.newRawUri("AliceDrop",selected));startActivity(Intent.createChooser(i,"Chia sẻ với"));}
 @Override protected void onActivityResult(int r,int c,Intent data){super.onActivityResult(r,c,data);if(c!=RESULT_OK||data==null)return;if(r==PICK){selected=data.getData();updateSelected();}if(r==SAVE&&received!=null){File f=received;Uri dest=data.getData();worker.execute(()->{try(InputStream in=new FileInputStream(f);OutputStream out=getContentResolver().openOutputStream(dest)){if(out==null)throw new IOException("Không mở được file");copy(in,out,LIMIT);ui.post(()->msg("Đã lưu file"));}catch(Exception e){ui.post(()->msg("Lỗi lưu file: "+e.getMessage()));}});}}
 private InetAddress wifiIp() throws Exception{
  ConnectivityManager cm=getSystemService(ConnectivityManager.class);
  for(Network n:cm.getAllNetworks()){NetworkCapabilities cap=cm.getNetworkCapabilities(n);LinkProperties lp=cm.getLinkProperties(n);if(cap==null||lp==null||!cap.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))continue;for(LinkAddress a:lp.getLinkAddresses())if(a.getAddress() instanceof Inet4Address&&!a.getAddress().isLoopbackAddress())return a.getAddress();}
  throw new IOException("Hãy kết nối hai máy cùng Wi-Fi tin cậy");
 }
 private void startLan(){
  stopLan(); final int gen=++generation; final Uri sending=selected;
  byte[] random=new byte[16];new SecureRandom().nextBytes(random);StringBuilder b=new StringBuilder();for(byte x:random)b.append(String.format("%02x",x&255));final String key=b.toString();token=key;
  worker.execute(()->{try(ServerSocket ss=new ServerSocket()){ss.bind(new InetSocketAddress(wifiIp(),0));ss.setSoTimeout(1000);synchronized(this){if(gen!=generation)return;server=ss;}String url="http://"+ss.getInetAddress().getHostAddress()+":"+ss.getLocalPort()+"/"+key+"/";ui.post(()->{if(gen==generation){link.setText(url);msg("Safari: mở link trên iPhone. Chỉ dùng Wi-Fi tin cậy; phiên 5 phút, HTTP không mã hóa.");}});
  long until=SystemClock.elapsedRealtime()+300000;
  while(!ss.isClosed()&&SystemClock.elapsedRealtime()<until){try(Socket s=ss.accept()){synchronized(this){if(gen!=generation)return;active=s;}s.setSoTimeout(10000);serve(s,key,sending,until);}catch(SocketTimeoutException ignored){}catch(IOException ignored){}finally{active=null;}}
  }catch(Exception e){ui.post(()->{if(gen==generation)msg("Lỗi Wi-Fi: "+e.getMessage());});}finally{ui.post(()->{if(gen==generation){stopLan();}});}});
 }
 private synchronized void stopLan(){generation++;try{if(active!=null)active.close();if(server!=null)server.close();}catch(IOException ignored){}server=null;active=null;if(link!=null)link.setText("Phiên Wi-Fi đã tắt.");}
 private static String line(InputStream in)throws IOException{ByteArrayOutputStream b=new ByteArrayOutputStream();while(b.size()<8192){int c=in.read();if(c<0)throw new EOFException();if(c==10)return b.toString("US-ASCII").replace("\r","");b.write(c);}throw new IOException("Header too long");}
 private static void headers(OutputStream out,int code,String type,long size,String extra)throws IOException{String h="HTTP/1.1 "+code+" "+(code==200?"OK":"Error")+"\r\nConnection: close\r\nCache-Control: no-store\r\nContent-Type: "+type+"\r\n"+(size>=0?"Content-Length: "+size+"\r\n":"")+extra+"\r\n";out.write(h.getBytes(StandardCharsets.US_ASCII));}
 private static void reply(OutputStream out,int code,String text)throws IOException{byte[] b=text.getBytes(StandardCharsets.UTF_8);headers(out,code,"text/html; charset=utf-8",b.length,"X-Content-Type-Options: nosniff\r\n");out.write(b);}
 private static void copy(InputStream in,OutputStream out,long limit)throws IOException{byte[] b=new byte[16384];long total=0;int n;while((n=in.read(b))!=-1){total+=n;if(total>limit)throw new IOException("File vượt giới hạn");out.write(b,0,n);}}
 private void serve(Socket s,String key,Uri sending,long until)throws IOException{
  InputStream in=new BufferedInputStream(s.getInputStream());OutputStream out=new BufferedOutputStream(s.getOutputStream());
  String[] req=line(in).split(" ");if(req.length!=3)return;long length=-1;boolean chunked=false;int count=0;String l;
  while(!(l=line(in)).isEmpty()){if(++count>64)throw new IOException("Too many headers");String lower=l.toLowerCase(java.util.Locale.ROOT);if(lower.startsWith("content-length:")){if(length!=-1)throw new IOException("Duplicate length");try{length=Long.parseLong(l.substring(15).trim());}catch(NumberFormatException e){throw new IOException(e);}}if(lower.startsWith("transfer-encoding:"))chunked=true;}
  String path="/"+key+"/";
  if(req[0].equals("GET")&&req[1].equals(path)){
   reply(out,200,"<!doctype html><meta name=viewport content='width=device-width'><h1>AliceDrop</h1><p>Wi-Fi local — not AirDrop</p>"+(sending!=null?"<a href='download'>Download selected file</a>":"")+"<p><input id=f type=file><button onclick='send()'>Send file to Android</button></p><p id=s></p><script>async function send(){let f=document.getElementById('f').files[0];if(!f)return;let r=await fetch('upload',{method:'POST',body:f,headers:{'Content-Type':'application/octet-stream'}});document.getElementById('s').textContent=r.ok?'Received; save on Android':'Transfer failed';}</script>");
  }else if(req[0].equals("GET")&&req[1].equals(path+"download")&&sending!=null){
   try(InputStream file=getContentResolver().openInputStream(sending)){if(file==null)throw new IOException("File absent");headers(out,200,"application/octet-stream",-1,"Content-Disposition: attachment; filename=AliceDrop-file.bin\r\n");copy(file,out,LIMIT);}
  }else if(req[0].equals("POST")&&req[1].equals(path+"upload")&&!chunked&&length>=0&&length<=LIMIT){
   File f=File.createTempFile("received-",".bin",getCacheDir());boolean ok=false;
   try(OutputStream file=new FileOutputStream(f)){byte[] buf=new byte[16384];long left=length;while(left>0){if(SystemClock.elapsedRealtime()>until)throw new IOException("Session expired");int n=in.read(buf,0,(int)Math.min(buf.length,left));if(n<0)throw new EOFException();file.write(buf,0,n);left-=n;}ok=true;}finally{if(!ok)f.delete();}
   ui.post(()->{if(received!=null)received.delete();received=f;msg("Đã nhận "+f.length()+" byte. Bấm Lưu file đã nhận.");});reply(out,200,"Received");
  }else{reply(out,404,"Unavailable");}out.flush();
 }
 @Override protected void onStop(){stopDiscovery();stopLan();super.onStop();}
 @Override protected void onDestroy(){worker.shutdownNow();super.onDestroy();}
}
