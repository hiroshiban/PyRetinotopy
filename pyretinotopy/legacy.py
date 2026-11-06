"""Conservative MATLAB configuration reader; never evaluates MATLAB code."""
import ast
import operator
from pathlib import Path
import re

import numpy as np

from .config import defaults
from .modes import parse_mode
from .outputs import write_json

FAMILY_FILE={"polar":"c_pol.m","eccentricity":"c_ecc.m","dual":"c_dual.m",
             "bar":"c_bar.m","multifocal":"c_multifocal.m","meridian":"c_meridian.m",
             "lgn":"c_lgnlocalizer.m","hrf":"c_hrf.m","localizer":"c_localizer.m"}


def _arithmetic(text,values):
    text=re.sub(r"[sd]param\.([A-Za-z_]\w*)",r"\1",text)
    tree=ast.parse(text,mode="eval")
    operations={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,
                ast.Div:operator.truediv,ast.Pow:operator.pow}
    def walk(node):
        if isinstance(node,ast.Expression):
            return walk(node.body)
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float,str,bool)):
            return node.value
        if isinstance(node,ast.Name):
            if node.id in ("true","false"):
                return node.id=="true"
            return values[node.id]
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            return -walk(node.operand) if isinstance(node.op,ast.USub) else walk(node.operand)
        if isinstance(node,ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](walk(node.left),walk(node.right))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
            args=[walk(a) for a in node.args]
            if node.keywords:raise ValueError("Keyword calls are not allowed.")
            funcs={"size":lambda a,dim:np.asarray(a).shape[int(dim)-1],
                   "numel":lambda a:int(np.asarray(a).size),"length":len,
                   "ceil":lambda a:int(np.ceil(a)),"floor":lambda a:int(np.floor(a)),
                   "round":lambda a:int(np.sign(a)*np.floor(abs(a)+.5)),"mod":operator.mod}
            if node.func.id in funcs:return funcs[node.func.id](*args)
        raise ValueError("Expression requires manual translation.")
    return walk(tree)


def read_assignments(path,values=None):
    values={} if values is None else dict(values)
    unresolved=[]
    # Configuration sources use '%' for comments, without quoted '%' literals.
    source=re.sub(r"%[^\n]*","",Path(path).read_text(encoding="utf-8-sig"))
    source=source.replace("...", " ")
    pattern=r"([sd]param)\.([A-Za-z_]\w*)\s*=\s*(\[[\s\S]*?\]|[^;\n]+)\s*;?"
    for match in re.finditer(pattern,source):
        key,text=match.group(2),match.group(3).strip()
        try:
            if text.startswith("["):
                rows=[]
                for row in re.split(r";|\n",text[1:-1]):
                    if row.strip():
                        tokens=re.split(r"[,\s]+",row.strip())
                        rows.append([_arithmetic(v,values) for v in tokens if v])
                value=rows[0] if len(rows)==1 else rows
            elif re.fullmatch(r"[sd]param\.[A-Za-z_]\w*\(1,:\)",text):
                value=values[text.split(".")[1].split("(")[0]][0]
            else:
                value=_arithmetic(text.replace(".^","**").replace("^","**").replace(".*","*").replace("./","/"),values)
            values[key]=value
        except (ValueError,SyntaxError,KeyError,TypeError,ZeroDivisionError,OverflowError):
            unresolved.append({"field":key,"expression":text,"source":Path(path).name})
    return values,unresolved


def migrate(subject_dir,mode,output):
    """Write a reviewable draft and a report; never execute a participant script."""
    source=Path(subject_dir).resolve()
    c=defaults(mode)
    if source.name!="_DEFAULT_":
        c.subject=source.name
    family=parse_mode(mode).family
    values,unresolved={},[]
    source_files=[]
    for filename in ("sizeparams.m",FAMILY_FILE[family],"retinotopy_display.m"):
        path=source/filename
        if not path.is_file():path=source.parent/"_DEFAULT_"/filename
        if not path.is_file():raise ValueError(f"Missing legacy configuration and _DEFAULT_ fallback: {filename}")
        source_files.append(str(path))
        values,unknown=read_assignments(path,values)
        unresolved.extend(unknown)
    mappings={
        "ScrWidth":("display","size_px",None),
        "vdist":("display","distance_cm",1),"ipd":("display","ipd_cm",1),
        "ExpMode":("display","mode",1),"fullscr":("display","full_screen",1),
        "force_frame_rate":("display","refresh_hz",1),
        "maxRad":("stimulus","max_radius_deg",1),"minRad":("stimulus","min_radius_deg",1),
        "fieldSize":("stimulus","max_radius_deg",.5),
        "nwedges":("stimulus","checker_wedges",1),"nrings":("stimulus","checker_rings",1),
        "phase":("stimulus","checker_phase_deg",1),"rotangle":("stimulus","step_angle_deg",1),
        "startangle":("stimulus","start_angle_deg",1),
        "rotangles":("stimulus","bar_angles_deg",1),"steps":("stimulus","bar_steps",1),
        "ndivsL":("stimulus","bar_checks_long",1),"ndivsS":("stimulus","bar_checks_short",1),
        "ndivsP":("stimulus","multifocal_sectors",1),"ndivsE":("stimulus","multifocal_rings",1),
        "tgtRad":("stimulus","target_radii_deg",1),
        "RDSdepth":("stimulus","disparity_arcmin",1),"RDSDense":("stimulus","dot_density_percent",1),
        "RDSradius":("stimulus","dot_radius_deg",1),"RDSbackground":("stimulus","dot_background",bool),
        "flip_duration":("stimulus","object_update_s",.001),"nimg":("stimulus","object_count",1),
        "imRatio":("stimulus","object_scale",1),"imdepth":("stimulus","object_disparity_arcmin",1),
        "cycle_duration":("timing","cycle_s",.001),"rest_duration":("timing","rest_s",.001),
        "numRepeats":("timing","repeats",1),"block_duration":("timing","block_s",.001),
        "trial_duration":("timing","trial_s",.001),
        "pol_cycle_duration":("timing","polar_cycle_s",.001),"pol_rest_duration":("timing","polar_rest_s",.001),
        "pol_numRepeats":("timing","polar_repeats",1),
        "ecc_cycle_duration":("timing","eccentricity_cycle_s",.001),"ecc_rest_duration":("timing","eccentricity_rest_s",.001),
        "ecc_numRepeats":("timing","eccentricity_repeats",1),
        "pol_nwedges":("stimulus","checker_wedges",1),"pol_nrings":("stimulus","checker_rings",1),
        "pol_width":("stimulus","wedge_width_deg",1),"pol_startangle":("stimulus","start_angle_deg",1),
        "pol_rotangle":("stimulus","step_angle_deg",1),
        "pol_phase":("stimulus","checker_phase_deg",1),
        "ecc_width":("stimulus","dual_ring_width_deg",1),
        "ecc_rotangle":("stimulus","dual_ring_step_angle_deg",1),
        "ecc_nwedges":("stimulus","dual_ring_checker_wedges",1),
        "ecc_nrings":("stimulus","dual_ring_checker_rings",1),
        "ecc_phase":("stimulus","dual_ring_phase_deg",1),
        "ecc_startangle":("stimulus","dual_ring_start_angle_deg",1),
        "dimratio":("task","dim_ratio",1),"RDStaskmagnitude":("task","depth_multiplier",1),
        "fixsize":("task","fixation_radius_px",1),
        "fixtaskfreq":("task","fixation_frequency",1),
        "design":("stimulus","multifocal_design",1),
        "patch_size":("display","background_patch_size_px",1),
        "patch_num":("display","background_patch_count",1)}
    mapped=[]
    for old,(section,new,scale) in mappings.items():
        if old not in values or scale is None:
            continue
        value=values[old]
        if scale is bool:
            value=bool(value)
        elif scale!=1:
            value=value*scale
        setattr(getattr(c,section),new,value)
        mapped.append(old)
    if "width" in values:
        setattr(c.stimulus,"bar_width_deg" if family=="bar" else "wedge_width_deg",values["width"])
    if values.get("force_frame_rate")==0:
        c.display.refresh_hz=60.0
        c.display.use_measured_refresh=True
    if "ScrWidth" in values and "ScrHeight" in values:
        c.display.size_px=[int(values["ScrWidth"]),int(values["ScrHeight"])]
    if "pix_per_cm" in values:
        c.display.width_cm=c.display.size_px[0]/values["pix_per_cm"]
    if "colors" in values:
        colors=np.asarray(values["colors"],dtype=float)/255
        c.display.background=colors[0].tolist()
        c.stimulus.colors=colors[1:].tolist()
    if "bgcolor" in values:
        c.display.background=(np.asarray(values["bgcolor"])/255).tolist()
    if "bgtype" in values:c.display.background_type={1:"plain",2:"grid"}.get(values["bgtype"],"unknown")
    for index,key in enumerate(("patch_color1","patch_color2")):
        if key in values:c.display.background_patch_colors[index]=(np.asarray(values[key])/255).tolist()
    if "start_method" in values:
        c.timing.start={0:"key",1:"mouse",2:"trigger",3:"unsupported-parallel-port",4:"trigger"}.get(values["start_method"],"unknown")
        if values["start_method"]==2:c.timing.trigger_keys=["5"]
    if isinstance(values.get("custom_trigger"),str):c.timing.trigger_keys=[values["custom_trigger"].lower()]
    for index,key in enumerate(("Key1","Key2")):
        if isinstance(values.get(key),str):c.timing.response_keys[index]=values[key].lower()
    if "fixcolor" in values:
        c.task.fixation_color=(np.asarray(values["fixcolor"])/255).tolist()
    if "RDScolors" in values:
        colors=values["RDScolors"]
        c.stimulus.dot_colors=[[v/255]*3 for v in colors[:2]]
        if parse_mode(mode).carrier=="disparity" and len(colors)>2:
            c.display.background=[colors[2]/255]*3
    if "fixtype" in values:
        c.task.fixation_type={1:"circle",2:"cross",3:"concentric"}.get(values["fixtype"],"unknown")
    if "initial_fixation_time" in values:
        times=values["initial_fixation_time"]
        if not isinstance(times,list):
            times=[times,times]
        c.timing.initial_fixation_s,c.timing.final_fixation_s=[v/1000 for v in times]
    if "fixtaskduration" in values:
        c.task.duration_s=values["fixtaskduration"]/c.display.refresh_hz
    # PTB3: nframe_flicker = round(nframe_position / ncolors / 4).
    # Derive frequency from that rule instead of treating waitframes as reversal.
    from .design import Design
    try:
        d=Design(c)
        active=next(seg for seg in d.segments if seg.components)
        cadence=values.get("waitframes",1)/c.display.refresh_hz
        reference_duration=2.0 if family in ("meridian","lgn","hrf","localizer") else active.duration
        position_updates=int(np.floor(reference_duration/cadence+.5))
        flicker_updates=max(1,int(np.floor(position_updates/(len(c.stimulus.colors)/2)/4+.5)))
        if parse_mode(mode).carrier=="checker":c.stimulus.flicker_hz=1/(2*flicker_updates*cadence)
        if parse_mode(mode).carrier=="disparity":
            depth_updates=max(1,int(np.floor(position_updates/c.stimulus.disparity_arcmin[2]/4+.5)))
            c.stimulus.dot_refresh_hz=1/(depth_updates*cadence)
    except (ValueError,TypeError,StopIteration,ZeroDivisionError):pass
    if "onset_punch" in values:
        c.display.marker_corner,c.display.marker_size_px=values["onset_punch"]
    # PTB and PsychoPy enumerate displays/keys differently. Do not guess.
    notes=["REVIEW REQUIRED: screen IDs and keyboard names were not copied from platform-specific PTB codes.",
           "REVIEW REQUIRED: angular start phase/axis and first-cycle timing need side-by-side MATLAB validation.",
           "Fixation tasks retain fixtaskfreq slot probability, dim color and intervening normal slot; random draws differ.",
           "Review dual eccentricity timing/width and any unresolved expressions in the source report.",
           "Background grid/patch colors are mapped; supply gamma_lut separately in Python-native JSON.",
           "Parallel-port/PROPixx device control requires a tested hardware adapter; unsupported start methods remain invalid."]
    try:
        c.validate()
        validity="valid draft; hardware and compatibility review still required"
    except (ValueError,TypeError) as exc:
        validity=str(exc)
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    c.save(output)
    special={"width","ScrWidth","ScrHeight","pix_per_cm","colors","fixcolor","RDScolors",
             "fixtype","initial_fixation_time","fixtaskduration","waitframes","onset_punch", "bgcolor","bgtype",
             "patch_color1","patch_color2","start_method"}
    handled=set(mapped)|special
    report={"source":str(source),"source_files":source_files,"mode":mode,"mapped_fields":mapped,
            "unresolved_expressions":unresolved,
            "unmapped_static_values":{key:value for key,value in values.items() if key not in handled},
            "review_notes":notes,"validation":validity,
            "source_files_modified":False}
    write_json(output.with_suffix(".migration.json"),report)
    return report
