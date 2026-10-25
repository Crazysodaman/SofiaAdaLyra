"""MOD-BROWSER: offline URL review for an approved navigation proposal.

Never issues requests or resolves DNS. A syntactically valid HTTPS URL is not
safe/authenticated: Platform must independently validate DNS and consent before use.
"""
from __future__ import annotations
from datetime import datetime, timezone
from ipaddress import ip_address
import re
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID='MOD-BROWSER'
MODULE_VERSION='0.1.0'
CAPABILITY_ID='browser.review_navigation_candidates.v1'
PROFILE='ADVISORY'
RESOURCES=(('cpu_millicores',50),('ram_mib',32),('gpu_mib',0))
_REF=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_HOST=re.compile(r'^[a-z0-9](?:[a-z0-9.-]{0,250}[a-z0-9])?$')
_FIELDS=frozenset({'source_ref','observed_at','allowed_hosts','candidates'})
_ITEM=frozenset({'candidate_id','url'})


def _host(raw:object)->str:
    if not isinstance(raw,str) or len(raw)>253 or not _HOST.fullmatch(raw.lower()) or raw!=raw.lower():
        raise ValueError('invalid allowed hostname')
    name=raw.lower()
    if ('.' not in name or any(not part or len(part)>63 or part.startswith('-') or part.endswith('-') for part in name.split('.'))
        or name.endswith(('.local','.internal','.localhost','.test','.invalid')) or name in ('localhost',)):
        raise ValueError('unroutable allowed hostname')
    if name.rsplit('.',1)[-1].isdigit(): raise ValueError('numeric hostname suffix forbidden')
    try: ip_address(name)
    except ValueError: pass
    else: raise ValueError('literal IP address forbidden')
    return name


def _url(raw:object)->tuple[str,str]:
    if not isinstance(raw,str) or not 1<=len(raw)<=2048 or any(ord(c)<=32 or ord(c)>=127 for c in raw):
        raise ValueError('invalid url bytes')
    try: u=urlsplit(raw)
    except ValueError as exc: raise ValueError('malformed url') from exc
    if (u.scheme!='https' or not u.netloc or u.username is not None or u.password is not None
        or u.fragment or u.query or '\\' in raw or u.hostname is None or u.hostname!=u.hostname.lower()):
        raise ValueError('noncanonical or unsafe URL')
    host=_host(u.hostname)
    try: port=u.port
    except ValueError as exc: raise ValueError('invalid port') from exc
    if port not in (None,443): raise ValueError('nonstandard port')
    if u.netloc.lower() not in (host,host+':443') or u.netloc!=u.netloc.lower():
        raise ValueError('hostname must be canonical')
    if re.search(r'%(?:2f|5c|00|0a|0d)',u.path,re.I):
        raise ValueError('ambiguous escaped URL path')
    return host,urlunsplit(('https',host,u.path or '/',u.query,''))


def review_navigation_candidates(snapshot:Mapping[str,object],*,now:datetime,
                                 max_age_seconds:int=1800)->dict[str,object]:
    if not isinstance(snapshot,Mapping) or set(snapshot)!=_FIELDS:
        raise ValueError('exact navigation proposal required')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=86400:
        raise ValueError('invalid freshness limit')
    source=snapshot['source_ref']
    if not isinstance(source,str) or not _REF.fullmatch(source): raise ValueError('invalid source_ref')
    try: obs=datetime.fromisoformat(snapshot['observed_at'])
    except (TypeError,ValueError) as exc: raise ValueError('invalid observed_at') from exc
    if obs.tzinfo is None or obs.utcoffset() is None: raise ValueError('timezone required')
    hosts=snapshot['allowed_hosts']; candidates=snapshot['candidates']
    if type(hosts) is not list or not 1<=len(hosts)<=32: raise ValueError('1..32 allowed hosts required')
    checked_hosts=[_host(h) for h in hosts]
    if len(set(checked_hosts))!=len(checked_hosts): raise ValueError('duplicate hosts')
    if type(candidates) is not list or not 1<=len(candidates)<=64:
        raise ValueError('1..64 candidates required')
    seen=set(); reviewed=[]
    for item in candidates:
        if not isinstance(item,Mapping) or set(item)!=_ITEM: raise ValueError('invalid candidate fields')
        eid=item['candidate_id']
        if not isinstance(eid,str) or not _REF.fullmatch(eid) or eid in seen:
            raise ValueError('duplicate or invalid candidate_id')
        seen.add(eid)
        host, normalized=_url(item['url'])
        reviewed.append((eid,host,normalized))
    age=(now.astimezone(timezone.utc)-obs.astimezone(timezone.utc)).total_seconds()
    fresh='future' if age<-5 else 'stale' if age>max_age_seconds else 'fresh'
    base={'schema':'sofia.browser.navigation_review.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
          'module_id':MODULE_ID,'source_ref':source,'freshness':fresh,'effect':'none',
          'evidence_class':'supplied_unverified','requests_sent':False,'dns_verified':False,
          'host_trust_verified':False,'navigation_authorized':False}
    if fresh!='fresh':return base|{'status':'unknown','reviewed':[],'allowed_count':None}
    allow=set(checked_hosts)
    return base|{'status':'reviewed','allowed_count':sum(host in allow for _,host,_ in reviewed),
                 'reviewed':[{'candidate_id':eid,'host':host,'url':url if host in allow else None,
                              'host_in_allowlist':host in allow}
                             for eid,host,url in sorted(reviewed)]}


def capability_registrations():
    c=Capability(CAPABILITY_ID,'Review supplied HTTPS navigation candidates without opening them.')
    def handle(req:CapabilityRequest):
        if not isinstance(req,CapabilityRequest) or req.capability!=c or set(req.parameters)!={'snapshot'}:
            raise ValueError('invalid browser request')
        return review_navigation_candidates(req.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((c,handle),)
