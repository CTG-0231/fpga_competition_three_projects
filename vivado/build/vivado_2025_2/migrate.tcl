# Isolated 2025.2 system-IP migration using four hash-checked actual 2025.2 HLS exports.
# Invoke build.py, which stages hash-checked native sources before this script.
# Direct arguments: prepared input, NEW output, original native project, load|all.
# This creates a NEW project from source, not cached runs or DCPs. The prepared
# inputs stay unchanged: all Vivado writes use output_dir/workspace instead.
# Upgrade only built-in xilinx.com:ip cells; retain the supplied 2025.2 HLS RTL.
if {$argc < 3 || $argc > 4} { error "Expected prepared input, NEW output, ORIGINAL project, optional load|all" }
set build_mode all
if {$argc == 4} { set build_mode [lindex $argv 3] }
if {$build_mode ni {load all}} { error "Mode must be load or all" }
set_param general.maxThreads 1
set helper_root [file dirname [file normalize [info script]]]
if {[info exists ::env(FPGA_PYTHON)]} {
    set python_executable $::env(FPGA_PYTHON)
} else {
    set python_executable [lindex [auto_execok python] 0]
    if {$python_executable eq ""} { set python_executable [lindex [auto_execok python3] 0] }
    if {$python_executable eq ""} { error "Set FPGA_PYTHON to a Python 3 executable" }
}
set original_project [file normalize [lindex $argv 2]]
set prepared [file normalize [lindex $argv 0]]
set output_dir [file normalize [lindex $argv 1]]
if {![file isfile [file join $prepared prepare_config.tcl]]} {
    error "Run prepare_inputs.py first; input must be its self-contained output directory"
}
if {[file exists $output_dir]} { error "Use a new output directory to preserve prior results" }
proc path_is_within {candidate parent} {
    set candidate_parts [file split [file normalize $candidate]]
    set parent_parts [file split [file normalize $parent]]
    if {[llength $candidate_parts] < [llength $parent_parts]} { return 0 }
    for {set index 0} {$index < [llength $parent_parts]} {incr index} {
        if {![string equal -nocase [lindex $candidate_parts $index] [lindex $parent_parts $index]]} {
            return 0
        }
    }
    return 1
}
if {[path_is_within $output_dir $prepared] || [path_is_within $prepared $output_dir]} {
    error "Prepared input and output trees must not overlap"
}
foreach entry {inputs ip_repo prepare_config.tcl prepare_manifest.json} {
    if {![file exists [file join $prepared $entry]]} {
        error "Incomplete prepared input: missing $entry"
    }
}
file mkdir $output_dir
set workspace [file join $output_dir workspace]
file mkdir $workspace
foreach entry {inputs ip_repo prepare_config.tcl prepare_manifest.json} {
    file copy [file join $prepared $entry] [file join $workspace $entry]
}
# prepare_config.tcl resolves every path relative to its own info script.
# Source ONLY the copied configuration; upgrade/save/generate must never point
# back into the hash-checked prepared directory.
source [file join $workspace prepare_config.tcl]
foreach input [concat [list $prepare_root $prepare_bd $prepare_rtl] $prepare_xdc $prepare_ip_dirs] {
    if {![path_is_within $input $workspace]} {
        error "Copied configuration references a path outside the build workspace: $input"
    }
}
set actual_version [version -short]
if {![info exists prepare_target_version]} { set prepare_target_version $prepare_source_version }
if {$actual_version ne $prepare_target_version} {
    error "Prepared target is Vivado $prepare_target_version; actual tool is $actual_version. Do not downgrade to 2018.3."
}
puts [exec $python_executable -I -X utf8 -B [file join $helper_root patch_bd.py] $prepare_bd [file join $output_dir compatibility_patch.json]]
create_project leaf [file join $output_dir p] -part $prepare_part
set_property target_language Verilog [current_project]
set_property ip_repo_paths $prepare_ip_dirs [current_project]
update_ip_catalog
foreach name {conv fc pwdwconv shortcut} {
    if {![llength [get_ipdefs -all -quiet xilinx.com:hls:${name}:0.0]]} {
        error "Packaged HLS IP not discovered: $name"
    }
}
add_files -norecurse $prepare_rtl
add_files -fileset constrs_1 -norecurse $prepare_xdc
add_files -norecurse $prepare_bd
set bd_file [get_files design_1.bd]
open_bd_design $bd_file
report_ip_status -file [file join $output_dir ip_status_before.rpt]
proc save_ip_snapshot {path} {
    set channel [open $path w]
    puts $channel "cell\tvlnv"
    foreach cell [lsort [get_bd_cells -hierarchical -quiet]] {
        set identity [get_property -quiet VLNV $cell]
        if {$identity ne ""} { puts $channel "$cell\t$identity" }
    }
    close $channel
}
proc save_address_snapshot {path} {
    set channel [open $path w]
    puts $channel "segment\toffset\trange"
    foreach segment [lsort [get_bd_addr_segs -hierarchical -quiet]] {
        puts $channel "$segment\t[get_property -quiet OFFSET $segment]\t[get_property -quiet RANGE $segment]"
    }
    close $channel
}
save_ip_snapshot [file join $output_dir ip_before.tsv]
save_address_snapshot [file join $output_dir address_before.tsv]
if {$prepare_target_version eq "2025.2"} {
    # UG835 2025.2 permits upgrade_ip on bd_cell objects. Do not upgrade HLS
    # cells, do not run HLS synthesis and do not change user algorithm sources.
    set system_cells [get_bd_cells -hierarchical -quiet -filter {VLNV =~ xilinx.com:ip:*}]
    if {[llength $system_cells]} {
        upgrade_ip -log [file join $output_dir system_ip_upgrade.log] $system_cells
    }
}
foreach name {conv fc pwdwconv shortcut} {
    set identity [get_property VLNV [get_bd_cells /${name}_0]]
    if {$identity ne "xilinx.com:hls:${name}:0.0"} {
        error "HLS identity changed unexpectedly: $name -> $identity"
    }
}
source [file join $helper_root configure_single_id.tcl]
configure_single_id $output_dir
# Explicitly preserve the RGB565 -> RGB888 conversion after system-IP upgrade.
set subset [get_bd_cells /axis_subset_converter_0]
set_property CONFIG.S_TDATA_NUM_BYTES.VALUE_MODE MANUAL $subset
set_property CONFIG.M_TDATA_NUM_BYTES.VALUE_MODE MANUAL $subset
set_property -dict [list CONFIG.S_TDATA_NUM_BYTES {2} CONFIG.M_TDATA_NUM_BYTES {3}] $subset
# Width propagation may reset remaps; reapply them only after locking widths.
set_property CONFIG.TDATA_REMAP {tdata[15:11],3'b000,tdata[10:5],2'b00,tdata[4:0],3'b000} $subset
# TKEEP is propagated at validate; the gate checks its final original mapping.
validate_bd_design
save_bd_design
save_ip_snapshot [file join $output_dir ip_after.tsv]
save_address_snapshot [file join $output_dir address_after.tsv]
report_ip_status -file [file join $output_dir ip_status_after.rpt]
write_bd_tcl -force [file join $output_dir design_upgraded.tcl]
generate_target all $bd_file
set wrapper [make_wrapper -files $bd_file -top]
foreach path $wrapper {
    if {![path_is_within $path $workspace]} { error "Generated wrapper escaped this workspace: $path" }
}
add_files -norecurse $wrapper
set_property top design_1_wrapper [current_fileset]
update_compile_order -fileset sources_1
report_ip_status -file [file join $output_dir ip_status.rpt]
puts [exec $python_executable -I -X utf8 -B [file join $helper_root check_inputs.py] $output_dir $original_project]
puts "MIGRATION_INPUT_GATE_PASSED"
if {$build_mode eq "load"} {
    close_project
    puts "MIGRATION_LOAD_COMPLETED"
    exit
}
source [file join $helper_root flow.tcl]
