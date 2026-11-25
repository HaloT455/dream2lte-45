package tech.airdrop4e;
public final class A4eSendOpts {
 public final String computerName,computerModel=null,serviceId=null;
 public final boolean hasAuthTag=false;
 public final byte[] authTag=new byte[3];
 public final long askTimeoutMs=60000;
 public A4eSendOpts(String name){computerName=name;}
}