# Run through hls_2025_2.py for SHA checks, isolated paths and compatibility inputs.
foreach key {HLS_KERNEL HLS_PROJECT HLS_SOURCE_DIR HLS_TEST_DIR HLS_EXPORT HLS_CONFIG HLS_ACTION} {
    if {![info exists ::env($key)] || $::env($key) eq ""} { error "Missing $key; invoke build/hls_2025_2.py" }
}
set top $::env(HLS_KERNEL)
set sources $::env(HLS_SOURCE_DIR)
set benches $::env(HLS_TEST_DIR)
set action $::env(HLS_ACTION)
switch -- $top {
    conv {
        set files {conv.cpp conv.h}
        set tb {test_tb.cpp}
        set args {{in1 in1_V 0x10} {in2 in2_V 0x18} {in3 in3_V 0x20} {weight weight_V 0x28} {bias bias_V 0x30} {out out_V 0x38}}
    }
    pwdwconv {
        set files {pwdwconv.cpp pwdwconv.h pwconv.cpp pwconv.h dwconv.cpp dwconv.h}
        set tb {test.cpp test_tb.cpp}
        set args {{PBUS1 PBUS1_V 0x10} {PBUS2 PBUS2_V 0x18} {PBUS3 PBUS3_V 0x20} {PBUS4 PBUS4_V 0x28} {SBUS1 SBUS1_V 0x30} {SBUS2 SBUS2_V 0x38} {ch_in ch_in 0x40} {ch_out ch_out 0x48} {stride stride 0x50} {fsize fsize 0x58} {act act 0x60} {mode mode 0x68}}
    }
    fc {
        set files {fc.cpp fc.h}
        set tb {test_tb.cpp}
        set args {{in in_V 0x10} {weight weight_V 0x18} {bias bias_V 0x20} {out out_V 0x28}}
    }
    shortcut {
        set files {shortcut.cpp shortcut.h}
        set tb {test_tb.cpp}
        set args {{src1 src1_V 0x10} {src2 src2_V 0x18} {dest dest_V 0x20} {length length_r 0x28}}
    }
    default { error "Unsupported kernel: $top" }
}
open_project $::env(HLS_PROJECT)
set_top $top
foreach name $files { add_files [file join $sources $name] }
foreach name $tb { add_files -tb [file join $benches $name] }
open_solution solution1 -flow_target vivado
set_part xc7z020clg484-2
create_clock -period 5 -name default
set_clock_uncertainty 12.5%
config_compile -pipeline_loops 0
config_interface -m_axi_addr64=false -m_axi_alignment_byte_size 1 -m_axi_latency 0 -m_axi_max_widen_bitwidth 0 -s_axilite_data64=false -s_axilite_interrupt_mode tow
config_rtl -module_auto_prefix=false -register_reset_num 0
config_export -format ip_catalog -rtl verilog -version 0.0 -vivado_optimization_level 2 -vivado_phys_opt place -vivado_report_level 0
foreach entry $args {
    lassign $entry argument name offset
    set_directive_interface -mode s_axilite -bundle CTRL -offset $offset -name $name $top $argument
}
if {$top eq "conv"} {
    # Avoid the 2025.2 statically inferred row burst whose request is gated by
    # padding at j=0. A one-word cache suppresses that inference; top AXI and
    # original pointer-register widths/offsets remain checked independently.
    set_directive_cache conv in1 -lines 1 -depth 1
    set_directive_cache conv in2 -lines 1 -depth 1
    set_directive_cache conv in3 -lines 1 -depth 1
}
if {$action in {csim all}} { csim_design }
if {$action in {build cosim all}} {
    csynth_design
    export_design -format ip_catalog -rtl verilog -vendor xilinx.com -library hls -ipname $top -version 0.0 -output $::env(HLS_EXPORT)
    # -all emits sentinel settings that cannot be replayed (e.g. FIFO depth 0).
    write_ini $::env(HLS_CONFIG) -package_defaults -filepaths absolute
}
if {$action in {cosim all}} { cosim_design -rtl verilog -tool xsim }
close_project
exit
