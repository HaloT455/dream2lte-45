#!/usr/bin/env python3
"""Execute the actual deadline controller and kernel endpoint with host shims."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp)
    (p/'controller.cpp').write_text(r'''
#include "alice/powerhal/Controller.h"
#include <cassert>
#include <climits>
int main() {
    assert(!DeadlineController::validTarget(0));
    assert(!DeadlineController::validTarget(999999));
    assert(!DeadlineController::validTarget(INT64_MAX));
    DeadlineController c(16666667);
    assert(c.leaseMs() >= 40 && c.leaseMs() <= 250);
    int64_t now = 2000000000;
    for (int i=0;i<100;i++) { now += 16666667; assert(c.sample(now, 24000000, now)); }
    assert(c.level == 3);
    for (int i=0;i<100;i++) { now += 16666667; assert(c.sample(now, 7000000, now)); }
    assert(c.level == 0);
    assert(!c.sample(now, 100, now));  // repeated/stale batch cannot extend the lease
    assert(!c.sample(now+1, 0, now+1));
    assert(!c.sample(now+1, INT64_MAX, now+1));
    assert(!c.sample(now+2, 100, now+1));
    c.reset(); assert(c.level == 0 && c.lastTimestamp == 0);
    assert(!c.sample(1, 100, now));
    DeadlineController slow(1000000000), fast(1000000);
    assert(slow.leaseMs() == 250 && fast.leaseMs() == 40);
}
''')
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I'+str(root),
                    str(p/'controller.cpp'), '-o', str(p/'controller')], check=True)
    subprocess.run([str(p/'controller')], check=True)
    print('PASS: actual deadline controller adapts both ways, rejects stale/invalid samples, bounds leases')
    linux = p/'linux'
    linux.mkdir()
    shim = r'''
#pragma once
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/types.h>
#include <assert.h>
#define __init
#define PAGE_SIZE 4096
#define late_initcall(x)
#define scnprintf snprintf
#define max(a,b) ({ __typeof__(a) x=(a); __typeof__(b) y=(b); x>y?x:y; })
#define min(a,b) ({ __typeof__(a) x=(a); __typeof__(b) y=(b); x<y?x:y; })
#define time_before(a,b) ((long)((a)-(b)) < 0)
#define time_after_eq(a,b) (!time_before(a,b))
#define msecs_to_jiffies(x) (x)
static unsigned long jiffies;
struct kobject {int unused;};
static struct kobject *power_kobj;
struct attribute {int unused;};
struct kobj_attribute {struct attribute attr;};
#define __ATTR(a,b,c,d) { {0} }
static int sysfs_create_file(struct kobject *k, struct attribute *a) {return 0;}
static int sysfs_streq(const char *a, const char *b) {
 size_t n=strlen(b);return !strncmp(a,b,n) && (a[n]=='\0'||(a[n]=='\n'&&a[n+1]=='\0'));
}
#define DEFINE_MUTEX(x) int x
#define mutex_lock(x) ((void)(x))
#define mutex_unlock(x) ((void)(x))
struct work_struct {int unused;};
struct delayed_work {int unused;};
#define DECLARE_DELAYED_WORK(a,b) struct delayed_work a
static int system_wq, scheduled;
static unsigned long delay;
static void mod_delayed_work(int q, struct delayed_work *w, unsigned long d) {scheduled=1;delay=d;}
static void cancel_delayed_work(struct delayed_work *w) {scheduled=0;}
struct pm_qos_request {int cls, value;};
#define PM_QOS_CLUSTER0_FREQ_MIN 3
#define PM_QOS_CLUSTER1_FREQ_MIN 5
static int writes;
static void pm_qos_add_request(struct pm_qos_request *q,int cls,int value) {q->cls=cls;q->value=value;}
static void pm_qos_update_request(struct pm_qos_request *q,int value) {q->value=value;writes++;}
static void pm_qos_remove_request(struct pm_qos_request *q) {}
struct thermal_zone_device {int unused;};
static struct thermal_zone_device thermal;
static int fake_temp=45000, sensor_error;
#define IS_ERR(p) (!(p))
static struct thermal_zone_device *thermal_zone_get_zone_by_name(const char *name) {return &thermal;}
static int thermal_zone_get_temp(struct thermal_zone_device *t,int *out) {*out=fake_temp;return sensor_error;}
struct notifier_block {int (*notifier_call)(struct notifier_block *,unsigned long,void *);};
#define PM_SUSPEND_PREPARE 1
#define NOTIFY_OK 0
static void register_pm_notifier(struct notifier_block *n) {}
'''
    (p/'shim.h').write_text(shim)
    for name in ['init','kernel','kobject','sysfs','mutex','jiffies','pm_qos','thermal','suspend']:
        (linux/(name+'.h')).write_text('#include "shim.h"\n')
    (p/'kernel.c').write_text(r'''
#include "kernel/power/alice_power_hint.c"
static ssize_t cmd(const char *s) {return alice_power_hint_store(0,0,s,strlen(s));}
static void tick(unsigned long ms) {jiffies+=ms;alice_hint_work(0);}
int main(void) {
 assert(alice_power_hint_init()==0);
 assert(little_req.cls==3 && big_req.cls==5 && !scheduled);
 assert(cmd("boost 0 80\n")>0 && applied_level==2 && scheduled && delay==80);
 assert(little_req.value==1053000 && big_req.value==1066000);
 int old=writes;
 assert(cmd("boost 0 80\n")>0 && writes==old); // same level does not retrigger QoS
 tick(81); assert(applied_level==0 && !scheduled && little_req.value==0 && big_req.value==0);
 assert(cmd("session 0 3 100")>0 && applied_level==3);
 assert(cmd("session 1 2 200")>0 && applied_level==3);
 assert(cmd("session 0 0 0")>0 && applied_level==2);
 assert(cmd("mode 7 0")>0 && applied_level==0 && !scheduled);
 assert(cmd("reset")>0 && !interactive); // service restart preserves the screen-off gate
 assert(cmd("session 0 3 250")>0 && applied_level==0 && !scheduled);
 assert(cmd("mode 7 1")>0 && applied_level==0); // screen-on cannot revive stale hints
 assert(cmd("mode 1 1")>0);
 assert(cmd("boost 0 250")>0 && applied_level==1 && delay==120 && big_req.value==0);
 tick(121); assert(!scheduled && applied_level==0);
 assert(cmd("mode 1 0")>0);
 fake_temp=61000; tick(201);
 assert(cmd("session 0 3 250")>0 && applied_level==1);
 fake_temp=66000; tick(201);assert(applied_level==0);
 tick(50);assert(!scheduled);
 fake_temp=45000;sensor_error=1;tick(201);
 assert(cmd("session 0 3 250")>0 && applied_level==0); // fail closed
 tick(251);sensor_error=0;tick(201);
 assert(cmd("mode 5 1")>0 && applied_level==3);
 tick(1001);assert(applied_level==0 && !scheduled); // missing LAUNCH=false cannot pin xung
 assert(cmd("session 15 3 250")>0);
 alice_hint_pm_notify(0,PM_SUSPEND_PREPARE,0);
 assert(applied_level==0 && !scheduled);
 assert(cmd("mode 8 1")>0);
 assert(cmd("boost 0 250")>0 && !scheduled && !applied_level);
 assert(cmd("mode 8 0")>0 && !applied_level);
 assert(cmd("boost 0 251")==-EINVAL);
 assert(cmd("boost 3 100")==-EINVAL);
 assert(cmd("session 16 3 50")==-EINVAL);
 assert(cmd("session 0 4 50")==-EINVAL);
 assert(cmd("session 0 3 251")==-EINVAL);
 assert(cmd("session 0 3 50 garbage")==-EINVAL);
 assert(cmd("mode 7 2")==-EINVAL);
 assert(cmd("mode 3 1")==-EINVAL);
 assert(cmd("reset garbage")==-EINVAL);
 assert(cmd("session -1 3 50")==-EINVAL);
 assert(cmd("reset")>0 && !applied_level && !scheduled);
 char status[4096];alice_power_hint_show(0,0,status);
 assert(strstr(status,"version=1 level=0") && strstr(status,"expirations="));
}
''')
    subprocess.run(['gcc', '-std=gnu11', '-Wall', '-Wextra', '-Wno-unused-parameter',
                    '-Wno-unused-variable', '-Wno-sign-compare', '-I'+str(p), '-I'+str(root),
                    str(p/'kernel.c'), '-o', str(p/'kernel')], check=True)
    subprocess.run([str(p/'kernel')], check=True)
    print('PASS: actual kernel commands enforce expiry, mode gates, thermal budget, suspend cleanup and parser bounds')
    # Execute the actual service classes. Only Binder transport and syscalls are
    # substituted; session lifecycle, access checks and boost translation run unchanged.
    (p/'test_binder.h').write_text(r'''
#pragma once
#include <sys/types.h>
#include <memory>
#include <string>
#include <vector>
#include <cstdint>
using binder_status_t=int;
constexpr int EX_SECURITY=1,EX_ILLEGAL_ARGUMENT=2,EX_ILLEGAL_STATE=3,EX_UNSUPPORTED_OPERATION=4;
constexpr int STATUS_OK=0,STATUS_PERMISSION_DENIED=-1;
static uid_t caller=1000;
static uid_t AIBinder_getCallingUid() {return caller;}
static void ABinderProcess_setThreadPoolMaxThreadCount(int) {}
static void ABinderProcess_joinThreadPool() {}
static int AServiceManager_addService(void *,const char *) {return 0;}
#define ANDROID_LOG_ERROR 1
#define ANDROID_LOG_INFO 2
static void __android_log_print(int,const char *,const char *,...) {}
static void __android_log_write(int,const char *,const char *) {}
namespace ndk {
struct ScopedAStatus {
 int code;static ScopedAStatus ok(){return {0};}
 static ScopedAStatus fromExceptionCode(int c){return {c};}
 bool isOk()const{return !code;}
};
struct SharedRefBase {template<class T,class...A> static std::shared_ptr<T> make(A&&... a){return std::make_shared<T>(std::forward<A>(a)...);}};
}
namespace aidl::android::hardware::power {
enum class Mode {LOW_POWER=1,LAUNCH=5,INTERACTIVE=7,DEVICE_IDLE=8,DISPLAY_INACTIVE=9};
enum class Boost {INTERACTION=0,DISPLAY_UPDATE_IMMINENT=1};
struct WorkDuration {int64_t timeStampNanos,durationNanos;};
struct IPowerHintSession {
 virtual ~IPowerHintSession()=default;
 virtual ndk::ScopedAStatus updateTargetWorkDuration(int64_t)=0;
 virtual ndk::ScopedAStatus reportActualWorkDuration(const std::vector<WorkDuration>&)=0;
 virtual ndk::ScopedAStatus pause()=0,resume()=0,close()=0;
};
struct BnPowerHintSession:IPowerHintSession {};
struct IPower {static constexpr const char *descriptor="android.hardware.power.IPower";};
struct BnPower:IPower {
 virtual ~BnPower()=default;
 virtual ndk::ScopedAStatus setMode(Mode,bool)=0,isModeSupported(Mode,bool*)=0;
 virtual ndk::ScopedAStatus setBoost(Boost,int32_t)=0,isBoostSupported(Boost,bool*)=0;
 virtual ndk::ScopedAStatus createHintSession(int32_t,int32_t,const std::vector<int32_t>&,int64_t,std::shared_ptr<IPowerHintSession>*)=0;
 virtual ndk::ScopedAStatus getHintSessionPreferredRate(int64_t*)=0;
 virtual binder_status_t dump(int,const char**,uint32_t)=0;
 struct Binder {void*get(){return nullptr;}}; Binder asBinder(){return {};}
};
}
''')
    for name in ['aidl/android/hardware/power/BnPower.h', 'aidl/android/hardware/power/BnPowerHintSession.h',
                 'android/binder_manager.h', 'android/binder_process.h', 'android/log.h']:
        file = p/name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('#include "test_binder.h"\n')
    (p/'service.cpp').write_text(r'''
#define main AlicePowerMain
#include "alice/powerhal/Power.cpp"
#undef main
#include <cassert>
#include <cstdarg>
static std::vector<std::string> writes;
static bool deny;
extern "C" int __wrap_open(const char *path,int,...) {
 assert(std::string(path)==NODE);if(deny){errno=EACCES;return -1;}return 999;
}
extern "C" ssize_t __wrap_write(int fd,const void *p,size_t n) {
 assert(fd==999);writes.emplace_back(static_cast<const char*>(p),n);return n;
}
extern "C" int __wrap_close(int fd) {assert(fd==999);return 0;}
int main() {
 Power power;bool supported=false;
 assert(writes.back()=="reset\n");
 assert(power.isModeSupported(Mode::LAUNCH,&supported).isOk()&&supported);
 power.isModeSupported(static_cast<Mode>(3),&supported);assert(!supported);
 caller=10001;assert(!power.setMode(Mode::LAUNCH,true).isOk());caller=1000;
 power.setBoost(Boost::INTERACTION,INT32_MAX);assert(writes.back()=="boost 0 250\n");
 power.setBoost(Boost::INTERACTION,0);assert(writes.back()=="boost 0 80\n");
 power.setBoost(Boost::INTERACTION,-1);assert(writes.back()=="boost 0 0\n");
 assert(!power.setBoost(static_cast<Boost>(2),100).isOk());
 std::shared_ptr<IPowerHintSession> session;
 caller=10001;assert(!power.createHintSession(42,10001,{42},16666667,&session).isOk());caller=1000;
 assert(!power.createHintSession(42,10001,{},16666667,&session).isOk());
 assert(!power.createHintSession(42,10001,{42},0,&session).isOk());
 assert(power.createHintSession(42,10001,{42},16666667,&session).isOk());
 int64_t now=monotonicNs();
 assert(session->reportActualWorkDuration({{now-200,30000000},{now-100,30000000}}).isOk());
 assert(writes.back()=="session 0 2 66\n");
 auto before=writes.size();
 assert(!session->reportActualWorkDuration({{now-300,30000000}}).isOk()&&writes.size()==before);
 caller=10002;assert(!session->pause().isOk());caller=10001;
 assert(session->pause().isOk()&&writes.back()=="session 0 0 0\n");
 before=writes.size();session->reportActualWorkDuration({{monotonicNs(),30000000}});assert(writes.size()==before);
 assert(session->resume().isOk()&&writes.back()=="session 0 0 0\n");
 assert(session->updateTargetWorkDuration(20000000).isOk());
 assert(session->close().isOk());before=writes.size();
 assert(session->close().isOk()&&writes.size()==before);
 assert(!session->reportActualWorkDuration({{monotonicNs(),30000000}}).isOk());
 session.reset();assert(writes.size()==before);
 caller=1000;
 std::vector<std::shared_ptr<IPowerHintSession>> sessions;
 for(int i=0;i<16;i++){assert(power.createHintSession(42,10001,{42},16666667,&session).isOk());sessions.push_back(session);}
 assert(!power.createHintSession(42,10001,{42},16666667,&session).isOk());
 sessions.clear(); // Binder/session destruction releases every occupied slot.
 for(int i=0;i<16;i++)assert(power.createHintSession(42,10001,{42},16666667,&session).isOk());
 session.reset();
 deny=true;power.setBoost(Boost::INTERACTION,80);
 power.isModeSupported(Mode::LAUNCH,&supported);assert(!supported);
 Power unavailable;
 unavailable.isModeSupported(Mode::LAUNCH,&supported);assert(!supported);
 assert(!unavailable.createHintSession(42,10001,{42},16666667,&session).isOk());
 deny=false;
}
''')
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I'+str(p), '-I'+str(root),
                    str(p/'service.cpp'), '-Wl,--wrap=open,--wrap=write,--wrap=close',
                    '-o', str(p/'service')], check=True)
    subprocess.run([str(p/'service')], check=True)
    print('PASS: actual HAL authorization, batch validation, expiry commands, pause/resume/close, Binder destruction, slot limits and unavailable backend')
