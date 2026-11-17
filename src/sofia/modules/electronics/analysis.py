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
VALIDATOR_CAPABILITY_ID = 'electronics.validate_netlist_bom.v1'
PROFILE = 'SIMULATE'
RESOURCES = (('cpu_millicores', 50),('ram_mib', 32),('gpu_mib', 0))
_FIELDS = frozenset({'source_ref','observed_at','input_voltage_v','r_top_ohm','r_bottom_ohm',
                     'adc_reference_v','adc_bits','adc_input_limit_v'})
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_SNAPSHOT_FIELDS = frozenset({'source_ref','observed_at','supply_voltage_v','components','connections'})
_COMPONENT_FIELDS = frozenset({'ref','part_class','quantity','rated_voltage_v'})
_CONNECTION_FIELDS = frozenset({'net_id','members'})
_PART_CLASSES = frozenset({'resistor','capacitor','inductor','diode','led','transistor','ic','connector','switch','other'})


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


def _bounded_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise ValueError(f'invalid {label}')
    return value


def validate_netlist_bom(snapshot: Mapping[str,object], *, now: datetime,
                         max_age_seconds: int = 86400) -> dict[str,object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _SNAPSHOT_FIELDS:
        raise ValueError('netlist/BOM snapshot requires exact fields')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now requires timezone')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid max_age_seconds')
    source = _bounded_id(snapshot['source_ref'], 'source_ref')
    supply = _number(snapshot['supply_voltage_v'], 'supply_voltage_v', 0, 1000)
    components = snapshot['components']
    if type(components) is not list or not 1 <= len(components) <= 128:
        raise ValueError('components must be a bounded non-empty list')
    part_refs: set[str] = set()
    ratings: dict[str, float | None] = {}
    for item in components:
        if not isinstance(item, Mapping) or set(item) != _COMPONENT_FIELDS:
            raise ValueError('invalid component fields')
        ref = _bounded_id(item['ref'], 'component ref')
        if ref in part_refs:
            raise ValueError('duplicate component ref')
        part_refs.add(ref)
        part_class = item['part_class']
        if not isinstance(part_class, str) or part_class not in _PART_CLASSES:
            raise ValueError('invalid part_class')
        quantity = item['quantity']
        if type(quantity) is not int or not 1 <= quantity <= 10000:
            raise ValueError('invalid quantity')
        rated = item['rated_voltage_v']
        ratings[ref] = None if rated is None else _number(rated, 'rated_voltage_v', 0.001, 1000)
    connections = snapshot['connections']
    if type(connections) is not list or len(connections) > 256:
        raise ValueError('connections must be a bounded list')
    net_ids: set[str] = set()
    referenced: set[str] = set()
    for net in connections:
        if not isinstance(net, Mapping) or set(net) != _CONNECTION_FIELDS:
            raise ValueError('invalid net fields')
        net_id = _bounded_id(net['net_id'], 'net_id')
        if net_id in net_ids:
            raise ValueError('duplicate net_id')
        net_ids.add(net_id)
        members = net['members']
        if type(members) is not list or not 2 <= len(members) <= 16:
            raise ValueError('net members must be a bounded list')
        if any(not isinstance(v, str) or _REF.fullmatch(v) is None for v in members):
            raise ValueError('invalid net member')
        if len(set(members)) != len(members):
            raise ValueError('duplicate net member')
        referenced.update(members)
    try:
        stamp = datetime.fromisoformat(snapshot['observed_at'])
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid observed_at') from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('observed_at requires timezone')
    observed = stamp.astimezone(timezone.utc)
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    result = {'schema': 'sofia.electronics.netlist_bom_validation.v1',
              'sdk_protocol': str(SDK_PROTOCOL_VERSION), 'module_id': MODULE_ID,
              'source_ref': source, 'observed_at': observed.isoformat(),
              'freshness': freshness, 'evidence_class': 'supplied_unverified',
              'advisory_only': True, 'effect': 'none',
              'netlist_electrically_exercised': False,
              'hardware_validation_verified': False}
    if freshness != 'fresh':
        return result | {'status': 'unknown', 'component_count': None,
                         'connection_count': None, 'missing_part_refs': [],
                         'voltage_overstress_refs': [], 'voltage_unknown_refs': [],
                         'findings': ['netlist_timestamp_invalid']}
    missing = sorted(referenced - part_refs)
    overstress = sorted(ref for ref, rated in ratings.items()
                        if rated is not None and supply > rated)
    unknown_ratings = sorted(ref for ref, rated in ratings.items() if rated is None)
    findings = []
    if missing:
        findings.append('missing_bom_parts')
    if overstress:
        findings.append('supply_exceeds_component_rated_voltage')
    if unknown_ratings:
        findings.append('component_voltage_rating_unknown')
    return result | {'status': 'validated_consistent' if not findings else 'validated_with_findings',
                     'component_count': len(components), 'connection_count': len(connections),
                     'missing_part_refs': missing, 'voltage_overstress_refs': overstress,
                     'voltage_unknown_refs': unknown_ratings, 'findings': findings}


def capability_registrations():
    cap=Capability(CAPABILITY_ID,'Simulate ideal resistor divider and ADC code, without device access.')
    def handler(request:CapabilityRequest):
        if request.capability!=cap or set(request.parameters)!={'plan'}:
            raise ValueError('invalid electronics capability request')
        return analyze_adc_divider(request.parameters['plan'],now=datetime.now(timezone.utc))
    validator=Capability(VALIDATOR_CAPABILITY_ID,
                         'Validate supplied netlist/BOM consistency without electrical simulation or device access.')
    def validator_handler(request:CapabilityRequest):
        if request.capability!=validator or set(request.parameters)!={'snapshot'}:
            raise ValueError('invalid netlist/BOM capability request')
        return validate_netlist_bom(request.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((cap,handler),(validator,validator_handler))
