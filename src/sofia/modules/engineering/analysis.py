"""MOD-ENGINEERING: ideal DC resistive circuit simulation, never wiring advice.

A supplied schematic is a mathematical model, NOT an installed electrical system.
No NEC, conductor ampacity, fault/arc-flash or equipment-safety assessment.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-ENGINEERING'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'engineering.simulate_resistive_dc.v1'
PROFILE = 'SIMULATE'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'topology', 'source_voltage_v',
                     'resistances_ohm', 'design_current_limit_a'})


def _valid_number(value: object, name: str, low: float, high: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'invalid {name}')
    return float(value)


def simulate_dc_circuit(plan: Mapping[str, object], *, now: datetime,
                        max_age_seconds: int = 86_400) -> dict[str, object]:
    if not isinstance(plan, Mapping) or set(plan) != _FIELDS:
        raise ValueError('circuit plan requires exact fields')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must have a timezone')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86_400:
        raise ValueError('invalid max_age_seconds')
    source = plan['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    if plan['topology'] not in ('series', 'parallel'):
        raise ValueError('unsupported topology')
    values = plan['resistances_ohm']
    if type(values) is not list or not 1 <= len(values) <= 32:
        raise ValueError('resistances must contain 1..32 values')
    resistances = [_valid_number(value, 'resistance', 0.001, 1e9) for value in values]
    voltage = _valid_number(plan['source_voltage_v'], 'source_voltage_v', 0, 1000)
    limit = plan['design_current_limit_a']
    if limit is not None:
        limit = _valid_number(limit, 'design_current_limit_a', 0.001, 1e6)
    try:
        observed = datetime.fromisoformat(plan['observed_at'])
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid observed_at') from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError('observed_at requires timezone')
    age = (now.astimezone(timezone.utc)-observed.astimezone(timezone.utc)).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    result = {'schema':'sofia.engineering.dc_simulation.v1', 'sdk_protocol':str(SDK_PROTOCOL_VERSION),
              'module_id':MODULE_ID, 'source_ref':source, 'observed_at':observed.astimezone(timezone.utc).isoformat(),
              'freshness':freshness, 'evidence_class':'hypothetical_supplied', 'effect':'none',
              'assumptions':['ideal DC supply','purely resistive loads','no thermal or conductor effects'],
              'design_code_compliance':'not_assessed'}
    if freshness != 'fresh':
        return result | {'status':'unknown', 'total_current_a':None, 'total_power_w':None,
                         'equivalent_resistance_ohm':None, 'components':[], 'findings':['model_timestamp_invalid']}
    equivalent = sum(resistances) if plan['topology'] == 'series' else 1 / sum(1/r for r in resistances)
    current = voltage/equivalent
    components = []
    for index, resistance in enumerate(resistances):
        branch_current = current if plan['topology'] == 'series' else voltage/resistance
        branch_voltage = branch_current*resistance
        components.append({'index':index, 'resistance_ohm':resistance,
                           'current_a':branch_current, 'voltage_v':branch_voltage,
                           'power_w':branch_current*branch_voltage})
    total_power = voltage*current
    findings = []
    if limit is not None and current > limit:
        findings.append('user_supplied_current_limit_exceeded')
    return result | {'status':'simulated', 'equivalent_resistance_ohm':equivalent,
                     'total_current_a':current, 'total_power_w':total_power,
                     'components':components, 'findings':findings}


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Simulate ideal DC resistors from a supplied circuit plan; no electrical switching.')
    def handler(request: CapabilityRequest):
        if request.capability != capability or set(request.parameters) != {'plan'}:
            raise ValueError('invalid engineering capability request')
        return simulate_dc_circuit(request.parameters['plan'], now=datetime.now(timezone.utc))
    return ((capability, handler),)
