"""MOD-ELECTRONICS: ideal divider and ADC sampling calculation, no GPIO/I2C.

Does not prove ADC input tolerance, settling time, sample-hold loading or
hardware survivability. Input limit is an explicitly supplied design constraint.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-ELECTRONICS'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'electronics.analyze_adc_divider.v1'
PROFILE = 'SIMULATE'
RESOURCES = (('cpu_millicores', 50),('ram_mib', 32),('gpu_mib', 0))
_FIELDS = frozenset({'source_ref','observed_at','input_voltage_v','r_top_ohm','r_bottom_ohm',
                     'adc_reference_v','adc_bits','adc_input_limit_v'})
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')


def _number(value, label, low, high):
    if type(value) not in (int,float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'invalid {label}')
    return float(value)


def analyze_adc_divider(plan: Mapping[str,object], *,now:datetime,max_age_seconds:int=86_400)->dict[str,object]:
    if not isinstance(plan, Mapping) or set(plan)!=_FIELDS:
        raise ValueError('divider plan requires exact fields')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now requires timezone')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid max_age_seconds')
    source=plan['source_ref']
    if not isinstance(source,str) or _REF.fullmatch(source) is None:
        raise ValueError('invalid source_ref')
    vin=_number(plan['input_voltage_v'],'input_voltage_v',0,1000)
    top=_number(plan['r_top_ohm'],'r_top_ohm',1,1e9)
    bottom=_number(plan['r_bottom_ohm'],'r_bottom_ohm',1,1e9)
    ref=_number(plan['adc_reference_v'],'adc_reference_v',0.001,100)
    lim=_number(plan['adc_input_limit_v'],'adc_input_limit_v',0.001,100)
    bits=plan['adc_bits']
    if type(bits) is not int or not 1 <= bits <= 24:
        raise ValueError('invalid adc_bits')
    try:
        stamp=datetime.fromisoformat(plan['observed_at'])
    except (ValueError,TypeError) as exc:
        raise ValueError('invalid observed_at') from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('observed_at requires timezone')
    age=(now.astimezone(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()
    freshness='future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    result={'schema':'sofia.electronics.adc_divider.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
            'module_id':MODULE_ID,'source_ref':source,'observed_at':stamp.astimezone(timezone.utc).isoformat(),
            'freshness':freshness,'evidence_class':'hypothetical_supplied','effect':'none',
            'hardware_tolerance_verified':False}
    if freshness!='fresh':
        return result|{'status':'unknown','divider_voltage_v':None,'adc_code_ideal':None,'findings':['model_timestamp_invalid']}
    divider=vin*bottom/(top+bottom)
    steps=(1<<bits)-1
    ideal_code=round(min(divider,ref)/ref*steps)
    findings=[]
    if divider > lim:
        findings.append('input_exceeds_user_supplied_adc_limit')
    if divider > ref:
        findings.append('adc_reference_overrange_ideal_clipping')
    return result|{'status':'simulated','divider_voltage_v':divider,'divider_current_a':vin/(top+bottom),
                   'thevenin_ohm':top*bottom/(top+bottom),'adc_code_ideal':ideal_code,
                   'max_adc_code':steps,'quantization_lsb_v':ref/steps,'findings':findings}


def capability_registrations():
    cap=Capability(CAPABILITY_ID,'Simulate ideal resistor divider and ADC code, without device access.')
    def handler(request:CapabilityRequest):
        if request.capability!=cap or set(request.parameters)!={'plan'}:
            raise ValueError('invalid electronics capability request')
        return analyze_adc_divider(request.parameters['plan'],now=datetime.now(timezone.utc))
    return ((cap,handler),)
