"""MOD-ROBOTICS-GAIA: one ideal 3DOF virtual leg inverse kinematics.

Never emits SSC-32 pulses, motor commands, gait actuation or collision-clearance
claims. Coordinates: x/y horizontal from hip center, z positive upward.
Hip yaw and femur elevation are signed degrees; knee bend is 0 when extended.
"""
from __future__ import annotations
from datetime import datetime,timezone
import math,re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability,CapabilityRequest

MODULE_ID='MOD-ROBOTICS-GAIA'
MODULE_VERSION='0.1.0'
CAPABILITY_ID='gaia.simulate_leg_ik.v1'
PROFILE='SIMULATE'
RESOURCES=(('cpu_millicores',50),('ram_mib',32),('gpu_mib',0))
_REF=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS=frozenset({'source_ref','observed_at','coxa_mm','femur_mm','tibia_mm','target_xyz_mm',
                   'joint_limits_deg'})


def _num(v,label,low,high):
    if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:
        raise ValueError(f'invalid {label}')
    return float(v)


def simulate_leg_ik(plan:Mapping[str,object],*,now:datetime,max_age_seconds:int=86400)->dict[str,object]:
    if not isinstance(plan,Mapping) or set(plan)!=_FIELDS:
        raise ValueError('Gaia leg plan requires exact fields')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must be timezone-aware')
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=86400:
        raise ValueError('invalid max_age_seconds')
    source=plan['source_ref']
    if not isinstance(source,str) or _REF.fullmatch(source) is None:
        raise ValueError('invalid source_ref')
    coxa=_num(plan['coxa_mm'],'coxa_mm',0.1,1000)
    femur=_num(plan['femur_mm'],'femur_mm',0.1,1000)
    tibia=_num(plan['tibia_mm'],'tibia_mm',0.1,1000)
    coords=plan['target_xyz_mm']
    if type(coords) is not list or len(coords)!=3:
        raise ValueError('target_xyz_mm must contain x, y, z')
    x,y,z=(_num(v,'target coordinate',-5000,5000) for v in coords)
    limits=plan['joint_limits_deg']
    if type(limits) is not dict or set(limits)!={'yaw','femur','knee'}:
        raise ValueError('joint_limits_deg requires yaw, femur and knee')
    checked={}
    for key, pair in limits.items():
        if type(pair) is not list or len(pair)!=2:
            raise ValueError('joint limits require min and max')
        lo=_num(pair[0],f'{key} minimum',-360,360)
        hi=_num(pair[1],f'{key} maximum',-360,360)
        if lo>hi:
            raise ValueError('joint limit minimum exceeds maximum')
        checked[key]=(lo,hi)
    try:
        stamp=datetime.fromisoformat(plan['observed_at'])
    except (TypeError,ValueError) as exc:
        raise ValueError('invalid observed_at') from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('observed_at requires timezone')
    age=(now.astimezone(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()
    freshness='future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    result={'schema':'sofia.gaia.leg_ik.v1','module_id':MODULE_ID,'sdk_protocol':str(SDK_PROTOCOL_VERSION),
            'source_ref':source,'observed_at':stamp.astimezone(timezone.utc).isoformat(),
            'freshness':freshness,'evidence_class':'hypothetical_supplied','effect':'none',
            'servo_commands':None,'hardware_actuation_authorized':False,'collision_check':'not_performed'}
    if freshness!='fresh':
        return result|{'status':'unknown','angles_deg':None,'findings':['model_timestamp_invalid']}
    reach=math.hypot(x,y)-coxa
    distance=math.hypot(reach,z)
    if distance>femur+tibia+1e-9 or distance<abs(femur-tibia)-1e-9 or distance<1e-12:
        return result|{'status':'unreachable','angles_deg':None,
                       'findings':['target_outside_ideal_two_link_workspace']}
    cosine=max(-1,min(1,(distance*distance-femur*femur-tibia*tibia)/(2*femur*tibia)))
    knee=math.acos(cosine)
    yaw=math.atan2(y,x)
    elevation=math.atan2(z,reach)-math.atan2(tibia*math.sin(knee),femur+tibia*math.cos(knee))
    angles={'yaw':math.degrees(yaw),'femur':math.degrees(elevation),'knee':math.degrees(knee)}
    violated=sorted(key for key,angle in angles.items() if not checked[key][0]<=angle<=checked[key][1])
    return result|{'status':'joint_limits_exceeded' if violated else 'reachable_simulated',
                   'angles_deg':angles,'findings':[f'{key}_outside_user_supplied_limits' for key in violated],
                   'assumptions':['single unconstrained knee branch','rigid links, zero backlash',
                                  'no actuator pulse mapping','no body collision or gait stability model']}


def capability_registrations():
    cap=Capability(CAPABILITY_ID,'Simulate ideal Gaia 3DOF leg IK without motor or servo output.')
    def handler(request:CapabilityRequest):
        if request.capability!=cap or set(request.parameters)!={'plan'}:
            raise ValueError('invalid Gaia capability request')
        return simulate_leg_ik(request.parameters['plan'],now=datetime.now(timezone.utc))
    return ((cap,handler),)
