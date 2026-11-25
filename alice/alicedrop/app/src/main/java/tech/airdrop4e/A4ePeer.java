package tech.airdrop4e;
public final class A4ePeer {
 public final String ident,name,addr;
 public final int port;
 public A4ePeer(String i,String n,String a,int p){ident=i;name=n;addr=a;port=p;}
 public String endpoint(){return addr.contains(":")?"["+addr+"]:"+port:addr+":"+port;}
}