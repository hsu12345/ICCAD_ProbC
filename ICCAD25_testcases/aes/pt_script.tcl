set_app_var read_parasitics_load_locations true
foreach mydb [glob /home/yilu/research1/lagrange/full_cadence_flow/asap7sc7p5t_28/DB/NLDM/*VT_TT_nldm*.db /home/yilu/research1/lagrange/full_cadence_flow/asap7sc7p5t_28/DB/NLDM/sram*.db] {
    read_db $mydb
}
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_AO_LVT_TT_nldm_211120.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_AO_RVT_TT_nldm_211120.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_AO_SLVT_TT_nldm_211120.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_INVBUF_LVT_TT_nldm_220122.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_INVBUF_RVT_TT_nldm_220122.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_INVBUF_SLVT_TT_nldm_220122.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_OA_LVT_TT_nldm_211120.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_OA_RVT_TT_nldm_211120.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_OA_SLVT_TT_nldm_211120.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_SEQ_LVT_TT_nldm_220123.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_SEQ_RVT_TT_nldm_220123.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_SEQ_SLVT_TT_nldm_220123.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_SIMPLE_LVT_TT_nldm_211120.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_SIMPLE_RVT_TT_nldm_211120.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/asap7sc7p5t_SIMPLE_SLVT_TT_nldm_211120.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/sram_asap7_16x256_1rw.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/sram_asap7_32x256_1rw.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/sram_asap7_64x256_1rw.lib
read_lib /home/scratch.yilu_research/lagrange/full_cadence_flow/asap7sc7p5t_28/LIB/NLDM/sram_asap7_64x64_1rw.lib
set link_path "*"
foreach_in_collection mylib [get_libs *] {
    lappend link_path [get_object_name $mylib]
}

read_verilog /home/scratch.yilu_research/lagrange/full_cadence_flow/workspace_asap7_ReSyn/aes/pnr/build/aes/bookshelf/aes.v.pt
link
source /home/scratch.yilu_research/lagrange/full_cadence_flow/workspace_asap7_ReSyn/aes/pnr/build/aes/bookshelf/aes.sdc.pt
read_parasitics -keep_capacitive_coupling /home/scratch.yilu_research/lagrange/full_cadence_flow/workspace_asap7_ReSyn/aes/pnr/build/aes/bookshelf/aes.spef
update_timing
set timing_report_unconstrained_paths true
source /home/scratch.yilu_research/lagrange/INSTA/script/pt/gen_INSTA_dataset.tcl
gen_insta_dataset ./aes/bookshelf
exit
