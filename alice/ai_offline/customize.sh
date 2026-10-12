#!/system/bin/sh
# KernelSU / Magisk installer entrypoint. Unzip may be automatic.
ui_print "- ALICE Qwen3 0.6B AI: on-demand userland inference only"
ui_print "- No boot/DTB/MGLRU modifications"
set_perm "$MODPATH/run-ai.sh" 0 0 0755
set_perm "$MODPATH/llama-cli" 0 0 0755
set_perm "$MODPATH/Qwen3-0.6B-Q4_K_M.gguf" 0 0 0644
