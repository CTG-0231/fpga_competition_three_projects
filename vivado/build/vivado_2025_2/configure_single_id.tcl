# The reviewed HLS exports use one logical ID (zero) per AXI master.
# Disable optional ID instance pins using the official package parameter.
# No generated HDL or IP-XACT file is edited.
proc configure_single_id {output_dir} {
    set channel [open [file join $output_dir instance_id_overrides.tsv] w]
    puts $channel "core\tparameter\tpackage_default\tinstance_value"
    foreach {core masters} {
        conv {IN1 IN2 IN3 W OUT_R}
        fc {IN_R W O}
        pwdwconv {PBUS1 PBUS2 PBUS3 PBUS4 SBUS1 SBUS2}
        shortcut {IN1 IN2 OUT_R}
    } {
        set cell [get_bd_cells /${core}_0]
        foreach master $masters {
            set property CONFIG.C_M_AXI_${master}_ENABLE_ID_PORTS
            set before [get_property $property $cell]
            if {$before ni {true false 1 0}} { error "Unexpected ID-enable value: $core $property $before" }
            set_property $property false $cell
            puts $channel "$core\t$property\t$before\tfalse"
        }
    }
    close $channel
}
