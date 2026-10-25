"""MOD-CAD: geometric checks of an owner-supplied parametric rectangular plate.

The output is not a fabrication drawing or structural/thermal/code approval.
There are no filesystem, CAD application, printer, or machine-control effects.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-CAD'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'cad.simulate_plate.v1'
PROFILE = 'SIMULATE'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'width_mm', 'height_mm', 'thickness_mm',
                     'density_g_cm3', 'edge_margin_mm', 'holes'})
_HOLE_FIELDS = frozenset({'x_mm', 'y_mm', 'diameter_mm'})


def _number(value: object, name: str, low: float, high: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'invalid {name}')
    return float(value)


def simulate_plate(plan: Mapping[str, object], *, now: datetime, max_age_seconds: int = 86400) -> dict[str, object]:
    if not isinstance(plan, Mapping) or set(plan) != _FIELDS:
        raise ValueError('plate plan requires exact fields')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid max_age_seconds')
    source = plan['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    try:
        observed = datetime.fromisoformat(plan['observed_at'])
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid observed_at') from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError('observed_at must be timezone-aware')
    age = (now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    width = _number(plan['width_mm'], 'width_mm', 0.01, 100_000)
    height = _number(plan['height_mm'], 'height_mm', 0.01, 100_000)
    thickness = _number(plan['thickness_mm'], 'thickness_mm', 0.01, 10_000)
    density = _number(plan['density_g_cm3'], 'density_g_cm3', 0.01, 25)
    margin = _number(plan['edge_margin_mm'], 'edge_margin_mm', 0, min(width, height))
    holes = plan['holes']
    if type(holes) is not list or len(holes) > 32:
        raise ValueError('holes must be a list of at most 32 circles')
    circles = []
    for hole in holes:
        if not isinstance(hole, Mapping) or set(hole) != _HOLE_FIELDS:
            raise ValueError('hole requires exactly x_mm,y_mm,diameter_mm')
        x = _number(hole['x_mm'], 'x_mm', 0, width)
        y = _number(hole['y_mm'], 'y_mm', 0, height)
        d = _number(hole['diameter_mm'], 'diameter_mm', 0.01, min(width, height))
        circles.append((x, y, d/2))
    base = {'schema':'sofia.cad.plate_simulation.v1', 'module_id':MODULE_ID,
            'sdk_protocol':str(SDK_PROTOCOL_VERSION), 'source_ref':source,
            'freshness':freshness, 'evidence_class':'hypothetical_supplied', 'effect':'none',
            'manufacturing_approved':False, 'structural_validated':False}
    if freshness != 'fresh':
        return base | {'status':'unknown', 'volume_cm3':None, 'mass_g':None,
                       'net_area_mm2':None, 'findings':['model_timestamp_invalid']}
    findings = []
    for i, (x, y, radius) in enumerate(circles):
        if min(x-radius,y-radius,width-x-radius,height-y-radius) < margin - 1e-8:
            findings.append(f'hole_{i}_violates_edge_margin')
        for j in range(i):
            px, py, pr = circles[j]
            if math.hypot(x-px, y-py) < radius+pr+margin-1e-8:
                findings.append(f'hole_{j}_{i}_clearance_below_margin')
    if findings:
        return base | {'status':'invalid_geometry', 'volume_cm3':None, 'mass_g':None,
                       'net_area_mm2':None, 'findings':findings}
    area = width*height - sum(math.pi*r*r for _, _, r in circles)
    if area <= 0:
        return base | {'status':'invalid_geometry','volume_cm3':None, 'mass_g':None,
                       'net_area_mm2':None, 'findings':['no_positive_material_area']}
    volume = area * thickness/1000
    return base | {'status':'simulated', 'net_area_mm2':area,
                   'volume_cm3':volume, 'mass_g':volume*density, 'hole_count':len(circles),
                   'findings':[]}


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Calculate a hypothetical drilled-plate material estimate; no fabrication.')
    def handler(request: CapabilityRequest):
        if request.capability != capability or set(request.parameters) != {'plan'}:
            raise ValueError('invalid CAD capability request')
        return simulate_plate(request.parameters['plan'], now=datetime.now(timezone.utc))
    return ((capability, handler),)
