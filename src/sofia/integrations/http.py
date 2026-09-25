"""Small stdlib JSON HTTP client used by concrete service adapters."""
from __future__ import annotations
import json
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from typing import Any,Mapping

class ServiceHTTPError(RuntimeError): pass

class JsonHttpClient:
    def __init__(self,base_url:str,*,headers:Mapping[str,str]|None=None,timeout:float=10.0)->None:
        base=base_url.strip().rstrip("/")
        if not base.startswith(("http://","https://")): raise ValueError("base_url must be http(s)")
        self.base_url=base; self.headers=dict(headers or {}); self.timeout=timeout
    def request(self,method:str,path:str,*,query:Mapping[str,Any]|None=None,payload:Any=None)->Any:
        url=self.base_url+"/"+path.lstrip("/")
        if query:
            encoded=urlencode({k:v for k,v in query.items() if v is not None},doseq=True)
            if encoded: url+="?"+encoded
        headers={"Accept":"application/json",**self.headers}
        data=None
        if payload is not None:
            data=json.dumps(payload,separators=(",",":")).encode("utf-8")
            headers["Content-Type"]="application/json"
        req=Request(url,data=data,headers=headers,method=method.upper())
        try:
            with urlopen(req,timeout=self.timeout) as resp:
                raw=resp.read()
        except HTTPError as exc:
            body=exc.read().decode("utf-8",errors="replace")
            raise ServiceHTTPError(f"HTTP {exc.code}: {body[:500]}") from exc
        except URLError as exc:
            raise ServiceHTTPError(f"service request failed: {exc.reason}") from exc
        if not raw: return None
        try: return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:
            raise ServiceHTTPError("service returned non-JSON response") from exc
