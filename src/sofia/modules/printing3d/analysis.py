"""MOD-3D-PRINT: interpret slicer-provided filament length and print duration.

No G-code parsing, firmware connections, printer motion or thermal control.
This is a planning estimate, NOT independently measured material consumption.
"""
from __future__ import annotations
from datetime import datetime,timezone
import math,re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability,CapabilityRequest

MODULE_ID='MOD-3D-PRINT'
MODULE_VERSION='0.1.0'
CAPABILITY_ID='printing3d.estimate_material.v1'
GCODE_CAPABILITY_ID='printing3d.validate_gcode_bounds.v1'
PROFILE='ADVISORY'
RESOURCES=(('cpu_millicores',50),('ram_mib',32),('gpu_mib',0))
_REF=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS=frozenset({'source_ref','observed_at','filament_length_mm','filament_diameter_mm',
                   'density_g_cm3','slicer_duration_seconds','hotend_flow_limit_mm3_s',
                   'layer_height_mm','nozzle_diameter_mm'})
_GCODE_FIELDS=frozenset({'source_ref','observed_at','lines','estimated_duration_seconds','limits'})
_GCODE_LIMIT_FIELDS=frozenset({'max_temperature_c','max_coordinate_mm',
                               'max_extrusion_per_move_mm','max_duration_seconds'})
_GCODE_PARAM=re.compile(r'([A-Z])([-+]?(?:\d+(?:\.\d*)?|\.\d+))')
_GCODE_COMMAND=re.compile(r'^([GM]\d+|T\d+)\b')
_GCODE_INSPECTED=frozenset({'G0','G1','G4','G28','G90','G91','G92','M82','M83',
                            'M104','M109','M140','M190','M84','M112','T0','T1'})
_GCODE_UNSUPPORTED=frozenset({'G2','G3','G5','M600','M601','M602','M701','M702'})


def _num(v,name,low,high):
    if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:
        raise ValueError(f'invalid {name}')
    return float(v)


def estimate_material(plan:Mapping[str,object],*,now:datetime,max_age_seconds:int=86400)->dict[str,object]:
    if not isinstance(plan,Mapping) or set(plan)!=_FIELDS:
        raise ValueError('print plan requires exact fields')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now requires timezone')
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=86400:
        raise ValueError('invalid max_age_seconds')
    source=plan['source_ref']
    if not isinstance(source,str) or _REF.fullmatch(source) is None:
        raise ValueError('invalid source_ref')
    length=_num(plan['filament_length_mm'],'filament_length_mm',0,1e8)
    diameter=_num(plan['filament_diameter_mm'],'filament_diameter_mm',1,3.2)
    density=_num(plan['density_g_cm3'],'density_g_cm3',0.3,5)
    duration=_num(plan['slicer_duration_seconds'],'slicer_duration_seconds',1,2_592_000)
    flow_limit=plan['hotend_flow_limit_mm3_s']
    if flow_limit is not None:
        flow_limit=_num(flow_limit,'hotend_flow_limit_mm3_s',0.01,1000)
    layer=_num(plan['layer_height_mm'],'layer_height_mm',0.01,2)
    nozzle=_num(plan['nozzle_diameter_mm'],'nozzle_diameter_mm',0.05,3)
    try:
        stamp=datetime.fromisoformat(plan['observed_at'])
    except (ValueError,TypeError) as exc:
        raise ValueError('invalid observed_at') from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('observed_at requires timezone')
    age=(now.astimezone(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()
    freshness='future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    result={'schema':'sofia.printing3d.material_estimate.v1','module_id':MODULE_ID,
            'sdk_protocol':str(SDK_PROTOCOL_VERSION),'source_ref':source,
            'observed_at':stamp.astimezone(timezone.utc).isoformat(), 'freshness':freshness,
            'evidence_class':'slicer_supplied_unverified','effect':'none'}
    if freshness!='fresh':
        return result|{'status':'unknown','filament_volume_cm3':None,'filament_mass_g':None,
                       'findings':['slicer_evidence_timestamp_invalid']}
    volume_mm3=math.pi*(diameter/2)**2*length
    avg_flow=volume_mm3/duration
    findings=[]
    if flow_limit is not None and avg_flow>flow_limit:
        findings.append('average_flow_above_user_supplied_hotend_limit')
    if layer>0.8*nozzle:
        findings.append('layer_height_above_80_percent_nozzle_diameter')
    return result|{'status':'estimated','filament_volume_cm3':volume_mm3/1000,
                   'filament_mass_g':volume_mm3/1000*density,'average_flow_mm3_s':avg_flow,
                   'slicer_duration_seconds':duration,'findings':findings,
                   'assumptions':['circular filament cross section','no waste or purge adjustment',
                                  'slicer duration is unverified','average flow does not prove peak flow safety']}


def validate_gcode_bounds(plan: Mapping[str,object], *, now: datetime,
                          max_age_seconds: int = 86400) -> dict[str,object]:
    if not isinstance(plan, Mapping) or set(plan) != _GCODE_FIELDS:
        raise ValueError('G-code plan requires exact fields')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now requires timezone')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid max_age_seconds')
    source = plan['source_ref']
    if not isinstance(source, str) or _REF.fullmatch(source) is None:
        raise ValueError('invalid source_ref')
    lines = plan['lines']
    if type(lines) is not list or not 1 <= len(lines) <= 2000:
        raise ValueError('lines must be a bounded non-empty list')
    for raw in lines:
        if not isinstance(raw, str) or len(raw) > 200:
            raise ValueError('invalid G-code line')
        if '\n' in raw or '\r' in raw or '\x00' in raw:
            raise ValueError('invalid G-code line')
    limits = plan['limits']
    if not isinstance(limits, Mapping) or set(limits) != _GCODE_LIMIT_FIELDS:
        raise ValueError('G-code limits require exact fields')
    max_temp = _num(limits['max_temperature_c'], 'max_temperature_c', 0, 1000)
    max_coord = _num(limits['max_coordinate_mm'], 'max_coordinate_mm', 1, 100000)
    max_extrusion = _num(limits['max_extrusion_per_move_mm'], 'max_extrusion_per_move_mm', 0, 10000)
    max_duration = limits['max_duration_seconds']
    if type(max_duration) is not int or not 1 <= max_duration <= 2592000:
        raise ValueError('invalid max_duration_seconds')
    estimated = _num(plan['estimated_duration_seconds'], 'estimated_duration_seconds', 0, 2592000)
    try:
        stamp = datetime.fromisoformat(plan['observed_at'])
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid observed_at') from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('observed_at requires timezone')
    observed = stamp.astimezone(timezone.utc)
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    result = {'schema': 'sofia.printing3d.gcode_bounds_validation.v1', 'module_id': MODULE_ID,
              'sdk_protocol': str(SDK_PROTOCOL_VERSION), 'source_ref': source,
              'observed_at': observed.isoformat(), 'freshness': freshness,
              'evidence_class': 'supplied_unverified', 'simulation_only': True,
              'effect': 'none', 'executed': False, 'sent_to_device': False,
              'physical_effect_authorized': False}
    if freshness != 'fresh':
        return result | {'status': 'unknown', 'line_count': None,
                         'inspected_line_count': None, 'findings': ['gcode_timestamp_invalid']}
    absolute_position = True
    absolute_extrusion = True
    last_e: float | None = None
    highest_temp: float | None = None
    largest_extrusion = 0.0
    largest_coordinate: float | None = None
    safety: set[str] = set()
    notes: set[str] = set()
    unparsed = 0
    for index, raw in enumerate(lines, 1):
        text = raw.split(';', 1)[0].split('*', 1)[0].strip().upper()
        if not text:
            continue
        match = _GCODE_COMMAND.match(text)
        if match is None:
            unparsed += 1
            continue
        command = match.group(1)
        if command not in _GCODE_INSPECTED:
            if command in _GCODE_UNSUPPORTED:
                notes.add('unsupported_motion_command_present')
            unparsed += 1
            continue
        rest = text[match.end():]
        leftover = _GCODE_PARAM.sub('', rest).replace(' ', '')
        if command == 'G28':
            if any(char not in 'XYZ' for char in leftover):
                raise ValueError(f'invalid G-code parameters on line {index}')
        elif leftover:
            raise ValueError(f'invalid G-code parameters on line {index}')
        parameters: dict[str, float] = {}
        for token in _GCODE_PARAM.finditer(rest):
            parameters[token.group(1)] = float(token.group(2))
        if command == 'G90':
            absolute_position = True
        elif command == 'G91':
            absolute_position = False
            notes.add('relative_positioning_not_fully_bounded')
        elif command == 'M82':
            absolute_extrusion = True
        elif command == 'M83':
            absolute_extrusion = False
            last_e = None
        elif command == 'G92':
            if 'E' in parameters:
                last_e = parameters['E']
        elif command in ('G0', 'G1'):
            axes = [abs(parameters[axis]) for axis in ('X', 'Y', 'Z') if axis in parameters]
            if axes:
                largest_coordinate = max([largest_coordinate or 0.0] + axes)
            if absolute_position and any(value > max_coord for value in axes):
                safety.add('coordinate_outside_user_supplied_bounds')
            if not absolute_position and any(value > max_coord for value in axes):
                safety.add('relative_move_magnitude_exceeds_user_supplied_bound')
            if 'E' in parameters:
                e_value = parameters['E']
                if absolute_extrusion:
                    delta = abs(e_value) if last_e is None else e_value - last_e
                    last_e = e_value
                else:
                    delta = e_value
                largest_extrusion = max(largest_extrusion, abs(delta))
                if abs(delta) > max_extrusion:
                    safety.add('extrusion_per_move_exceeds_user_supplied_limit')
        elif command in ('M104', 'M109', 'M140', 'M190'):
            target = parameters.get('S', parameters.get('R'))
            if target is not None:
                if target < 0:
                    raise ValueError(f'invalid temperature command on line {index}')
                highest_temp = target if highest_temp is None else max(highest_temp, target)
                if target > max_temp:
                    safety.add('temperature_exceeds_user_supplied_limit')
    if estimated > max_duration:
        safety.add('estimated_duration_exceeds_user_supplied_limit')
    findings = sorted(safety | notes)
    return result | {'status': 'bounds_violated' if safety else 'bounds_validated',
                     'line_count': len(lines), 'inspected_line_count': len(lines) - unparsed,
                     'unparsed_command_count': unparsed, 'findings': findings,
                     'highest_temperature_c': highest_temp,
                     'largest_extrusion_delta_mm': largest_extrusion,
                     'largest_coordinate_mm': largest_coordinate,
                     'estimated_duration_seconds': estimated,
                     'bounds_are_user_supplied_not_machine_verified': True}


def capability_registrations():
    cap=Capability(CAPABILITY_ID,'Estimate slicer-supplied material and average flow without printer control.')
    def handler(request:CapabilityRequest):
        if request.capability!=cap or set(request.parameters)!={'plan'}:
            raise ValueError('invalid 3D printing capability request')
        return estimate_material(request.parameters['plan'],now=datetime.now(timezone.utc))
    validator=Capability(GCODE_CAPABILITY_ID,
                         'Validate supplied G-code/toolpath safety bounds without execution or printer access.')
    def validator_handler(request:CapabilityRequest):
        if request.capability!=validator or set(request.parameters)!={'plan'}:
            raise ValueError('invalid G-code validator capability request')
        return validate_gcode_bounds(request.parameters['plan'],now=datetime.now(timezone.utc))
    return ((cap,handler),(validator,validator_handler))
