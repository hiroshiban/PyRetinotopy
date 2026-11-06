"""Compare spatial schedules with a separate source-derived continuous oracle.

No MATLAB execution or framebuffer equality is claimed. Run from any directory.
Outputs docs/qa/spatial-phase-audit.json and spatial-phase-comparison.png.
"""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import numpy as np
from PIL import Image,ImageDraw
from pyretinotopy import __version__
from pyretinotopy.config import defaults
from pyretinotopy.design import Design
from pyretinotopy.geometry import Geometry
from pyretinotopy.modes import all_modes
from reference_ptb3 import aperture
from test_ptb3_phase import sample_points,comparison_times


def main():
    output=ROOT/'docs/qa'
    output.mkdir(parents=True,exist_ok=True)
    x,y=sample_points()
    entries=[]
    for mode in all_modes():
        c=defaults(mode)
        design=Design(c)
        geometry=Geometry(c)
        times=comparison_times(c,design)
        mismatch=0
        for t in times:
            expected=aperture(c,float(t),x,y,design.multifocal)
            actual=geometry.labels(x,y,design.at(float(t)).components)[0]>0
            mismatch+=int(np.count_nonzero(expected!=actual))
        entries.append({'mode':mode,'times_checked':len(times),'sample_points_per_time':len(x),
                        'mismatching_point_time_pairs':mismatch})
    if any(e['mismatching_point_time_pairs'] for e in entries):
        raise RuntimeError('Spatial mismatch; inspect tests before publishing the report')
    sources=['Presentation/'+n+'.m' for n in ['cretinotopy','cdual','cbar','cmultifocal',
               'cmeridian','clgnlocalizer','chrf','clocalizer']]
    sources+=['Generation/'+n+'.m' for n in ['pol_GenerateCheckerBoard1D',
              'ecc_GenerateCheckerBoard1D','bar_GenerateCheckerBar1D','mf_GenerateCheckerBoard1D']]
    source_root=ROOT.parent/'Retinotopy'
    hashes={name:hashlib.sha256((source_root/name).read_bytes()).hexdigest() for name in sources}
    report={'version':__version__,'date':datetime.now().astimezone().isoformat(),
            'method':'Independent continuous-coordinate PTB3 aperture oracle; no MATLAB runtime',
            'limits':['Excludes original pixel rounding, ceil boundaries and fixation footprint',
                      'Checker colors, task schedules and stochastic carriers are not MATLAB framebuffer comparisons',
                      'Default multifocal uses corrected unique region IDs; literal zero-phase PTB3 ID overlap is opt-in and tested separately'],
            'source_sha256':hashes,'mode_comparisons':entries,
            'total_point_time_pairs':sum(e['times_checked']*len(x) for e in entries),
            'total_mismatches':sum(e['mismatching_point_time_pairs'] for e in entries),
            'default_first_wedge_center_visual_degrees':{'cw':90,'ccw':102},
            'default_dual_ring':{'positions':16,'dwell_s':2,'nominal_width_deg':1},
            'regression_tests':96}
    (output/'spatial-phase-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    # Binary aperture figure: top=positive visual y. Colors indicate active field.
    cases=[('ccw',4.01),('cw',4.01),('exp',4.01),('cont',14.01),
           ('ccwexp',4.01),('bar',4.01),('multifocal',4.01),('lgn',4.01)]
    n=176
    sheet=Image.new('RGB',(780,60+len(cases)*198),(248,248,248))
    draw=ImageDraw.Draw(sheet)
    draw.text((10,10),'Apertures: visual +y up; default multifocal = unique IDs',fill='black')
    for j,label in enumerate(['v0.2.x','PTB3 formula*','v0.3.0']):
        draw.text((180+j*198,37),label,fill='black')
    axis=(np.arange(n)+.5-n/2)/n*17
    xx,yy=np.meshgrid(axis,axis[::-1])
    for row,(mode,t) in enumerate(cases):
        c=defaults(mode)
        d=Design(c)
        old=copy.deepcopy(c)
        old.stimulus.spatial_convention='legacy-python'
        images=[Geometry(old).labels(xx,yy,Design(old).at(t).components)[0]>0,
                aperture(c,t,xx,yy,d.multifocal),
                Geometry(c).labels(xx,yy,d.at(t).components)[0]>0]
        y0=60+row*198
        draw.text((10,y0+65),f'{mode}\nt={t:.2f}s',fill='black')
        for j,mask in enumerate(images):
            rgb=np.full((n,n,3),210,dtype=np.uint8)
            rgb[mask]=[35,87,154]
            rgb[n//2-1:n//2+1,n//2-1:n//2+1]=0
            sheet.paste(Image.fromarray(rgb),(178+j*198,y0))
    sheet.save(output/'spatial-phase-comparison.png')
    print(json.dumps({k:report[k] for k in ['version','total_point_time_pairs','total_mismatches']},indent=2))


if __name__=='__main__':main()
