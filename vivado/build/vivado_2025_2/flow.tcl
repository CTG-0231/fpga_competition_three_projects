launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {
    error "Synthesis failed; inspect new project logs"
}
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1
if {![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {
    error "Implementation/bitstream failed; inspect new project logs"
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
