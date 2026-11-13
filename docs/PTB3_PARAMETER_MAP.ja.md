# 原版設定の全項目対応表 - 0.4.0

[English](PTB3_PARAMETER_MAP.md) | [日本語](PTB3_PARAMETER_MAP.ja.md)

呈示入口46ファイル、設定参照96項目を抽出。未分類0。これは静的な網羅表であり、全機能の実機検証済みを意味しません。

| 原版の項目 | Python側の対応・扱い | 区分 |
|---|---|---|
| `dparam.ExpMode` | display.mode | partial_device_adapter_required |
| `dparam.Key1` | timing.response_keys | implemented |
| `dparam.Key2` | timing.response_keys | implemented |
| `dparam.RunScript` | versioned module/provenance metadata | derived |
| `dparam.ScrHeight` | display.size_px | implemented |
| `dparam.ScrWidth` | display.size_px | implemented |
| `dparam.custom_trigger` | timing.trigger_keys | implemented |
| `dparam.force_frame_rate` | display.refresh_hz / use_measured_refresh | implemented |
| `dparam.fps` | measured refresh metadata | derived |
| `dparam.fullscr` | display.full_screen | implemented |
| `dparam.ifi` | inverse refresh | derived |
| `dparam.onset_punch` | display.marker_corner / marker_size_px / marker_timing | implemented |
| `dparam.scrID` | display.screens (platform-specific IDs selected explicitly) | implemented |
| `dparam.skip_sync_test` | refresh measurement/validation is retained; bypassing timing validation is not copied | changed_validation_procedure |
| `dparam.start_method` | timing.start (key/mouse/scanner key); parallel port adapter unavailable | partial_device_adapter_required |
| `sparam.RDSDense` | stimulus.dot_density_percent | implemented |
| `sparam.RDSbackground` | stimulus.dot_background | implemented |
| `sparam.RDScolors` | stimulus.dot_colors / display.background | implemented |
| `sparam.RDSdepth` | stimulus.disparity_arcmin | implemented |
| `sparam.RDSradius` | stimulus.dot_radius_deg | implemented |
| `sparam.RDStaskmagnitude` | task.depth_multiplier | implemented |
| `sparam.RunScript` | versioned module/provenance metadata | derived |
| `sparam.TR` | timing.tr_s / export --tr | implemented |
| `sparam.bgcolor` | display.background | implemented |
| `sparam.bgtype` | display.background_type | implemented |
| `sparam.block_duration` | timing.block_s | implemented |
| `sparam.cm_per_pix` | width_cm/size_px[0] | derived |
| `sparam.colors` | stimulus.colors / display.background | implemented |
| `sparam.cycle_duration` | timing.cycle_s | implemented |
| `sparam.deisgn` | source misspelling of design; Python validates multifocal_design | original_typo |
| `sparam.design` | stimulus.multifocal_design | implemented |
| `sparam.dimratio` | task.dim_ratio | implemented |
| `sparam.ecc_cycle_duration` | timing.eccentricity_cycle_s | implemented |
| `sparam.ecc_npositions` | shared polar dwell formula | derived |
| `sparam.ecc_nrings` | stimulus.dual_ring_checker_rings | implemented |
| `sparam.ecc_numRepeats` | timing.eccentricity_repeats | implemented |
| `sparam.ecc_nwedges` | stimulus.dual_ring_checker_wedges | implemented |
| `sparam.ecc_phase` | stimulus.dual_ring_phase_deg | implemented |
| `sparam.ecc_rest_duration` | timing.eccentricity_rest_s | implemented |
| `sparam.ecc_rotangle` | stimulus.dual_ring_step_angle_deg | implemented |
| `sparam.ecc_startangle` | stimulus.dual_ring_start_angle_deg | implemented |
| `sparam.ecc_width` | stimulus.dual_ring_width_deg | implemented |
| `sparam.fieldSize` | stimulus.max_radius_deg | implemented |
| `sparam.fixcolor` | task.fixation_color | implemented |
| `sparam.fixsize` | task.fixation_radius_px | implemented |
| `sparam.fixtaskduration` | task.duration_s (seconds) | implemented |
| `sparam.fixtaskfreq` | task.fixation_frequency | implemented |
| `sparam.fixtype` | task.fixation_type (1=circle, 2=framed cross, 3=quadrant target) | implemented |
| `sparam.flip_duration` | stimulus.object_update_s | implemented |
| `sparam.imRatio` | stimulus.object_scale | implemented |
| `sparam.imdepth` | stimulus.object_disparity_arcmin | implemented |
| `sparam.initial_fixation_time` | timing.initial_fixation_s / final_fixation_s | implemented |
| `sparam.ipd` | display.ipd_cm | implemented |
| `sparam.maxRad` | stimulus.max_radius_deg | implemented |
| `sparam.minRad` | stimulus.min_radius_deg | implemented |
| `sparam.mode` | mode / parse_mode | derived |
| `sparam.ncolors` | len(colors)/2 | derived |
| `sparam.ndivsE` | stimulus.multifocal_rings | implemented |
| `sparam.ndivsL` | stimulus.bar_checks_long | implemented |
| `sparam.ndivsP` | stimulus.multifocal_sectors | implemented |
| `sparam.ndivsS` | stimulus.bar_checks_short | implemented |
| `sparam.nimg` | stimulus.object_count | implemented |
| `sparam.npatches` | unique geometry labels | derived |
| `sparam.npositions` | Design positions | derived |
| `sparam.nrings` | stimulus.checker_rings | implemented |
| `sparam.numRepeats` | timing.repeats | implemented |
| `sparam.numTrials` | design column count | derived |
| `sparam.nwedges` | stimulus.checker_wedges | implemented |
| `sparam.patch_color1` | display.background_patch_colors | implemented |
| `sparam.patch_color2` | display.background_patch_colors | implemented |
| `sparam.patch_num` | display.background_patch_count | implemented |
| `sparam.patch_size` | display.background_patch_size_px | implemented |
| `sparam.phase` | stimulus.checker_phase_deg | implemented |
| `sparam.pix_per_cm` | display.width_cm with size_px | implemented |
| `sparam.pix_per_deg` | display.ppd | derived |
| `sparam.pol_cycle_duration` | timing.polar_cycle_s | implemented |
| `sparam.pol_npositions` | 360/step_angle_deg | derived |
| `sparam.pol_nrings` | stimulus.checker_rings | implemented |
| `sparam.pol_numRepeats` | timing.polar_repeats | implemented |
| `sparam.pol_nwedges` | stimulus.checker_wedges | implemented |
| `sparam.pol_phase` | stimulus.checker_phase_deg | implemented |
| `sparam.pol_rest_duration` | timing.polar_rest_s | implemented |
| `sparam.pol_rotangle` | stimulus.step_angle_deg | implemented |
| `sparam.pol_startangle` | stimulus.start_angle_deg | implemented |
| `sparam.pol_width` | stimulus.wedge_width_deg | implemented |
| `sparam.rest_duration` | timing.rest_s | implemented |
| `sparam.rotangle` | stimulus.step_angle_deg | implemented |
| `sparam.rotangles` | stimulus.bar_angles_deg | implemented |
| `sparam.startangle` | stimulus.start_angle_deg | implemented |
| `sparam.startangles` | generated component angles | derived |
| `sparam.steps` | stimulus.bar_steps | implemented |
| `sparam.tgtRad` | stimulus.target_radii_deg | implemented |
| `sparam.trial_duration` | timing.trial_s | implemented |
| `sparam.vdist` | display.distance_cm | implemented |
| `sparam.waitframes` | flicker_hz / dot_refresh_hz; logical updates on a full-refresh loop | implemented |
| `sparam.width` | stimulus.wedge_width_deg / bar_width_deg | implemented |

各機能の使い方と機器依存の制約は [機能対応表](PTB3_FEATURES.ja.md) を参照してください。
