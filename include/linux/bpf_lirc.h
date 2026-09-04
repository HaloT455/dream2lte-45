/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _BPF_LIRC_H
#define _BPF_LIRC_H

#include <uapi/linux/bpf.h>

static inline int lirc_prog_attach(const union bpf_attr *attr,
				   struct bpf_prog *prog)
{
	return -EINVAL;
}

static inline int lirc_prog_detach(const union bpf_attr *attr)
{
	return -EINVAL;
}

static inline int lirc_prog_query(const union bpf_attr *attr,
				  union bpf_attr __user *uattr)
{
	return -EINVAL;
}

#endif /* _BPF_LIRC_H */
