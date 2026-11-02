# Resume only after the Python entry verifies no prior run PID is alive.
if {$argc != 2} { error "Expected result directory and original native project" }
set output_dir [file normalize [lindex $argv 0]]
set original_project [file normalize [lindex $argv 1]]
set helper_root [file dirname [file normalize [info script]]]
set python_executable $::env(FPGA_PYTHON)
set_param general.maxThreads 1
if {[version -short] ne "2025.2"} { error "Vivado 2025.2 required" }
puts [exec $python_executable -I -X utf8 -B [file join $helper_root check_inputs.py] $output_dir $original_project]
open_project [file join $output_dir p leaf.xpr]
foreach run [get_runs] {
    set state [get_property STATUS $run]
    if {[get_property PROGRESS $run] ne "100%" && [regexp -nocase {queued|running|error|fail} $state]} {
        puts "RESET_INCOMPLETE_RUN $run $state"
        reset_run $run
    }
}
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {
    launch_runs synth_1 -jobs 1
    wait_on_run synth_1
    if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} { error "Synthesis failed" }
}
proc bitstream_is_complete {} {
    set run [get_runs impl_1]
    set bit [file join [get_property DIRECTORY $run] design_1_wrapper.bit]
    return [expr {[get_property STATUS $run] eq "write_bitstream Complete!" &&
                  [get_property PROGRESS $run] eq "100%" &&
                  [file isfile $bit] && [file size $bit] > 0}]
}
# route_design Complete! is an intermediate target, not a completed bitstream.
if {![bitstream_is_complete]} {
    launch_runs impl_1 -to_step write_bitstream -jobs 1
    wait_on_run impl_1
    if {![bitstream_is_complete]} { error "Implementation did not complete write_bitstream" }
}
open_run impl_1
report_utilization -file [file join $output_dir utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $output_dir timing_summary.rpt]
check_timing -verbose -file [file join $output_dir check_timing.rpt]
report_drc -file [file join $output_dir drc.rpt]
report_methodology -file [file join $output_dir methodology.rpt]
report_cdc -file [file join $output_dir cdc.rpt]
report_bus_skew -file [file join $output_dir bus_skew.rpt]
report_clocks -file [file join $output_dir clocks.rpt]
report_clock_interaction -file [file join $output_dir clock_interaction.rpt]
report_io -file [file join $output_dir io.rpt]
write_hw_platform -fixed -include_bit -force -file [file join $output_dir leaf.xsa]
close_project
puts "VIVADO_2025_2_BUILD_COMPLETED; retain HLS cosim and physical board validation limits."
