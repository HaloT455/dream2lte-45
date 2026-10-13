# ALICE LRU — V12R69 R5

The companion APK now contains only manual MGLRU ON/OFF, an eight-second
trial that ends OFF, a root snapshot and log export. There is no Qwen/llama
engine, model download, chat, speech, process manager, VM policy, LMKD writer,
foreground service, boot receiver, network permission or automatic polling.
EnergyStep runs in the kernel, independently of the app.

Snapshots include MGLRU counters, memory PSI, CPU governor/current/min/max,
thermal values and `dumpsys cpuinfo`. They are captured only on a user request.
Root output is drained concurrently so large snapshots cannot fill the pipe
while Java waits for the shell. OFF can run while a trial is pending.

R5 defaults MGLRU OFF after the reported two-app freeze; manual ON is still an
experimental device test. The existing heat gate blocks ON at SoC >=53 C or
battery >=39 C. OFF has no heat or boot-completion gate. A userspace cleanup
cannot recover a deadlocked kernel.

Build: `.github/workflows/alice-android-app.yml`, Java 17, Android SDK 35,
Gradle 8.10.2. No NDK, CMake or llama build is needed. The package remains
`com.halot455.alice`, versionCode 12695. The R5 CI debug signing key is cached
for later updates. An older independently signed debug APK can require
uninstalling the old ALICE app before installing this one; uninstall removes
that app's downloaded model/settings. Stop the old app before testing R5.

Old manually installed `service.d` scripts are outside an APK or boot update.
If an ALICE auto-enable script was installed there, disable that exact script
before testing manual LRU. Do not remove unrelated KernelSU modules or scripts.
