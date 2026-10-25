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
PROFILE='ADVISORY'
RESOURCES=(('cpu_millicores',50),('ram_mib',32),('gpu_mib',0))
_REF=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS=frozenset({'source_ref','observed_at','filament_length_mm','filament_diameter_mm',
                   'density_g_cm3','slicer_duration_seconds','hotend_flow_limit_mm3_s',
                   'layer_height_mm','nozzle_diameter_mm'})


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


def capability_registrations():
    cap=Capability(CAPABILITY_ID,'Estimate slicer-supplied material and average flow without printer control.')
    def handler(request:CapabilityRequest):
        if request.capability!=cap or set(request.parameters)!={'plan'}:
            raise ValueError('invalid 3D printing capability request')
        return estimate_material(request.parameters['plan'],now=datetime.now(timezone.utc))
    return ((cap,handler),)
