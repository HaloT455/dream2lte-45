# AliceDrop native AirDrop protocol experiment
This is a separate protocol-build experiment, not a finished driver, APK integration or native AirDrop port.
Apple public source: https://github.com/apple-oss-distributions/mDNSResponder/blob/main/mDNSShared/dns_sd.h — kDNSServiceFlagsIncludeAWDL selects an existing AWDL interface; it cannot implement the radio transport.
Apple networking documentation: https://developer.apple.com/documentation/technotes/tn3111-ios-wifi-api-overview — Apple peer-to-peer Wi-Fi is not documented for third-party use.
Protocol donor: https://github.com/BenItBuhner/AirDrop-for-Everything at 34bdc8dfdd9c3eebd5b5bd8588b2fad2243a8e9c (MIT), a third-party clean-room implementation, NOT Apple source. The native core handles DNS-SD, TLS, binary plists, Discover/Ask/Upload and archives; its Android shell explicitly lacks AWDL. The CI builds the pinned donor's ARM64 FFI library and runs the upstream core tests on Linux. No donor source is altered, and the artifact includes license/provenance.
Radio reference: https://tarish.dev/ — the documented working Android AirDrop radio shim depends on specific modern Pixel silicon and vendor firmware. No evidence it works on BCM4361. Do not install its driver on S8+.
Acceptance criteria before calling this feature working:
1. Actual compatible radio transport on S8+ with peer IPv6 reachability, no synthetic interface or spoofed capability.
2. Discover real iPhone set to Everyone for 10 minutes, explicitly select peer, receive acceptance before sending.
3. Verify byte-identical file on iPhone, verify rejection/cancel, no bypass of contact-only authorization.
4. Preserve Wi-Fi reconnect, SELinux and EGO/thermal behavior.
Current status: protocol experiment only; no AWDL backend or Touch-to-Share integration. No new boot is justified by this change.
