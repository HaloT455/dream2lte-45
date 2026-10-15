ui_print "ALICE R15: verified One UI LMKD low-swap correction"
ui_print "Kernel: MGLRU OFF, PSI enabled, EAS + EnergyStep"
ui_print "No resident loop; status is written to the module's status.log"
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/service.sh" 0 0 0755
set_perm "$MODPATH/uninstall.sh" 0 0 0755
set_perm "$MODPATH/low-swap.sh" 0 0 0755
