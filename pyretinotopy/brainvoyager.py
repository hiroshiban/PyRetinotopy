"""BrainVoyager protocol export from the same planned/realized intervals.

PRT format: https://helpdesk.brainvoyager.com/729383-The-Format-of-PRT-Files
Bundled OLT files are copied unchanged from Hiroshi Ban's original package.
"""
import colorsys
from collections import defaultdict
import math
from pathlib import Path
import shutil
from .design import Design
from .export import realized_intervals


def condition_names(components):
    if not components:return ['Fixation']
    labels=[]
    for c in components:
        if c[0]=='multifocal':labels.extend(f'region_{r+1:02d}' for r in c[1])
        elif c[0]=='wedge':
            center=(c[1]+c[2]/2)%360
            if len(c)>3:center=(180-center)%360
            labels.append(f'polar_center_{center:07.3f}deg')
        elif c[0]=='ring':labels.append(f'annulus_{c[1]:.4f}_{c[2]:.4f}deg')
        elif c[0]=='bar':labels.append(f'bar_normal_{c[1]:g}_position_{c[2]:.4f}deg')
        elif c[0]=='meridian':labels.append(f'meridian_{c[1]:g}deg')
        elif c[0]=='localizer':labels.append('target_eccentricity' if c[1]==0 else 'complement')
        else:labels.append(c[0])
    return labels


def export_prt(config,path,frames_path=None,unit='msec',tr_s=None):
    if unit not in ('msec','Volumes'):raise ValueError('PRT time unit must be msec or Volumes.')
    path=Path(path)
    if path.exists():raise FileExistsError(path)
    design=Design(config)
    tr=config.timing.tr_s if tr_s is None else tr_s
    if not math.isfinite(tr) or tr<=0:raise ValueError('TR must be positive and finite.')
    intervals=(realized_intervals(design,frames_path)[0] if frames_path else
               [(s.onset,s.onset+s.duration,s.components) for s in design.segments])
    conditions=defaultdict(list)
    for a,b,comp in intervals:
        if b<=a:continue
        for name in condition_names(comp):
            entries=conditions[name]
            if entries and abs(entries[-1][1]-a)<1e-8:entries[-1][1]=b
            else:entries.append([a,b])
    header=['FileVersion: 2',f'ResolutionOfTime: {unit}',
            f'Experiment: PyRetinotopy {config.subject} {config.mode} run {config.run}',
            'BackgroundColor: 0 0 0','TextColor: 255 255 255','TimeCourseColor: 192 192 192',
            'TimeCourseThick: 2','ReferenceFuncColor: 0 0 80','ReferenceFuncThick: 2',
            f'NrOfConditions: {len(conditions)}']
    for i,(name,entries) in enumerate(sorted(conditions.items())):
        rows=[]
        for a,b in entries:
            if unit=='Volumes':
                if not all(math.isclose(v/tr,round(v/tr),abs_tol=1e-7) for v in (a,b)):
                    raise ValueError('PRT volume boundaries must align to TR; use msec for fractional or measured timings.')
                first,last=round(a/tr)+1,round(b/tr)
            else:first,last=round(a*1000),round(b*1000)
            if last>=first:rows.append((first,last))
        rgb=tuple(round(v*255) for v in colorsys.hsv_to_rgb(i/max(len(conditions),1),.85,1))
        if name=='Fixation':rgb=(195,195,195)
        header.extend(['',name,str(len(rows)),*[f'{a} {b}' for a,b in rows],
                       'Color: '+' '.join(map(str,rgb))])
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='') as stream:stream.write('\n'.join(header)+'\n')
    return path


def export_olts(directory):
    source=Path(__file__).resolve().parent/'data/brainvoyager'
    files=sorted(source.glob('*.olt'))
    if len(files)!=6:raise RuntimeError('The six original OLT resources are missing.')
    output=Path(directory)
    if any((output/p.name).exists() for p in files):raise FileExistsError('OLT output already exists.')
    output.mkdir(parents=True,exist_ok=True)
    for p in files:
        with (output/p.name).open('xb') as stream:stream.write(p.read_bytes())
    return [output/p.name for p in files]
