"""Catalogue PTB3 entry points, referenced settings and Python counterparts.

Read-only towards the original project. Static references are an inventory,
not proof of native framebuffer/hardware equivalence. Private subject files
are deliberately excluded; _DEFAULT_ is included.
"""
import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pyretinotopy import __version__
from pyretinotopy.modes import all_modes,DISPLAY_MODES


def main():
    source=ROOT.parent/'Retinotopy'
    files=[p for p in source.rglob('*.m') if 'subjects' not in p.parts or '_DEFAULT_' in p.parts]
    presentation=sorted((source/'Presentation').glob('*.m'))
    # Reuse the static migration field map without executing any source MATLAB.
    tree=ast.parse((ROOT/'pyretinotopy/legacy.py').read_text(encoding='utf-8'))
    node=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='mappings' for t in n.targets))
    class Literals(ast.NodeTransformer):
        def visit_Name(self,node):return ast.copy_location(ast.Constant('bool'),node)
    mapped=ast.literal_eval(Literals().visit(node))
    targets={key:section+'.'+name for key,(section,name,_) in mapped.items()}
    targets.update({
        'ExpMode':'display.mode','Key1':'timing.response_keys','Key2':'timing.response_keys',
        'ScrHeight':'display.size_px','ScrWidth':'display.size_px','custom_trigger':'timing.trigger_keys',
        'force_frame_rate':'display.refresh_hz / use_measured_refresh','fullscr':'display.full_screen',
        'onset_punch':'display.marker_corner / marker_size_px / marker_timing',
        'scrID':'display.screens (platform-specific IDs selected explicitly)',
        'start_method':'timing.start (key/mouse/scanner key); parallel port adapter unavailable',
        'skip_sync_test':'refresh measurement/validation is retained; bypassing timing validation is not copied',
        'width':'stimulus.wedge_width_deg / bar_width_deg','bgcolor':'display.background',
        'bgtype':'display.background_type','patch_color1':'display.background_patch_colors',
        'patch_color2':'display.background_patch_colors','colors':'stimulus.colors / display.background',
        'RDScolors':'stimulus.dot_colors / display.background','fixcolor':'task.fixation_color',
        'fixtype':'task.fixation_type (1=circle, 2=framed cross, 3=quadrant target)',
        'initial_fixation_time':'timing.initial_fixation_s / final_fixation_s',
        'fixtaskduration':'task.duration_s (seconds)','waitframes':'flicker_hz / dot_refresh_hz; logical updates on a full-refresh loop',
        'pix_per_cm':'display.width_cm with size_px','TR':'timing.tr_s / export --tr',
        'design':'stimulus.multifocal_design'})
    derived={'RunScript':'versioned module/provenance metadata','fps':'measured refresh metadata',
             'ifi':'inverse refresh','mode':'mode / parse_mode','ncolors':'len(colors)/2',
             'npatches':'unique geometry labels','npositions':'Design positions',
             'pol_npositions':'360/step_angle_deg','ecc_npositions':'shared polar dwell formula',
             'startangles':'generated component angles','numTrials':'design column count',
             'pix_per_deg':'display.ppd','cm_per_pix':'width_cm/size_px[0]'}
    refs={};functions=[]
    for path in presentation:
        text=path.read_text(encoding='utf-8-sig',errors='replace')
        for kind,name in set(re.findall(r'\b([sd]param)\.([A-Za-z]\w*)',text)):
            refs.setdefault((kind,name),[]).append(path.name)
        if path.name[0] in 'cdi' and 'function' in text[:250]:
            functions.append({'file':path.name,'signature':text.splitlines()[0],
                              'fixation_types':all(v in text for v in ['fixtype==1','fixtype==2','fixtype==3']),
                              'backup_function':'BackUpObsoleteFiles' in text,
                              'fixation_task':'fixtaskfreq' in text,
                              'gamma_table':'GammaLoadPTB' in text})
    settings=[]
    for (kind,name),used in sorted(refs.items()):
        if name in targets:status='implemented';target=targets[name]
        elif name in derived:status='derived';target=derived[name]
        elif name=='deisgn':status='original_typo';target='source misspelling of design; Python validates multifocal_design'
        else:status='unclassified';target='REVIEW REQUIRED'
        if kind=='dparam' and name in ('ExpMode','start_method'):status='partial_device_adapter_required'
        if name=='skip_sync_test':status='changed_validation_procedure'
        settings.append({'original':kind+'.'+name,'status':status,'python':target,'presentation_files':sorted(used)})
    if any(v['status']=='unclassified' for v in settings):raise RuntimeError('Unclassified PTB3 parameter')
    catalogue=[{'file':p.relative_to(source).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in sorted(files)]
    olts={}
    for p in (source/'pRF/olt').glob('*.olt'):
        copy=ROOT/'pyretinotopy/data/brainvoyager'/p.name
        assert p.read_bytes()==copy.read_bytes()
        olts[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    report={'version':__version__,'date':datetime.now().astimezone().isoformat(),
            'scope':'Presentation entry points, all referenced dparam/sparam fields, all nine defaults, Generation/Common and pRF auxiliary source catalogue; excludes private subjects',
            'presentation_files':len(presentation),'presentation_functions':functions,
            'settings':settings,'settings_count':len(settings),'unclassified_settings':0,
            'default_files':[p.name for p in sorted((source/'Presentation/subjects/_DEFAULT_').glob('*.m'))],
            'source_catalogue':catalogue,'source_catalogue_count':len(catalogue),
            'supported_mode_aliases':list(all_modes()),'display_modes':list(DISPLAY_MODES),
            'original_olt_sha256':olts,
            'explicit_limits':['PROPixx/Datapixx dedicated hardware control and parallel-port voltage triggers require device adapters',
                               'EyeLink/MEG/audio and general Common/m2html analysis utilities are not all ported as same-name Python functions',
                               'No MATLAB framebuffer or random-sequence equality is claimed',
                               'GPU verification of v0.4.0 is pending a local GPU-enabled desktop; current session is RDP']}
    output=ROOT/'docs/qa/ptb3-feature-audit.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    lines=['# 原版設定の全項目対応表 - '+__version__,
           '',f'呈示入口{len(presentation)}ファイル、設定参照{len(settings)}項目を抽出。未分類0。これは静的な網羅表であり、全機能の実機検証済みを意味しません。',
           '', '| 原版の項目 | Python側の対応・扱い | 区分 |','|---|---|---|']
    for row in settings:lines.append('| `'+row['original']+'` | '+row['python']+' | '+row['status']+' |')
    lines+=['','詳細な関数別参照とソースのSHA-256は [監査JSON](qa/ptb3-feature-audit.json)。機能と検証範囲は [継承状況](PTB3_FEATURES.ja.md)。']
    (ROOT/'docs/PTB3_PARAMETER_MAP.ja.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'presentation_files':len(presentation),'presentation_functions':len(functions),
                      'settings':len(settings),'unclassified':0,'source_files_catalogued':len(catalogue)},indent=2))


if __name__=='__main__':main()
