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
    def request_text(
        self,
        method:str,
        path:str,
        *,
        query:Mapping[str,Any]|None=None,
        timeout:float|None=None,
        max_bytes:int=262144,
    )->str:
        if (
            type(max_bytes) is not int
            or not 1 <= max_bytes <= 4 * 1024 * 1024
        ):
            raise ValueError("max_bytes must be in 1..4194304")
        url=self.base_url+"/"+path.lstrip("/")
        if query:
            encoded=urlencode({k:v for k,v in query.items() if v is not None},doseq=True)
            if encoded: url+="?"+encoded
        headers={"Accept":"text/plain, application/octet-stream",**self.headers}
        req=Request(url,headers=headers,method=method.upper())
        try:
            effective_timeout=self.timeout if timeout is None else timeout
            if (
                isinstance(effective_timeout,bool)
                or not isinstance(effective_timeout,(int,float))
                or effective_timeout<=0
            ):
                raise ValueError("timeout must be a positive number")
            with urlopen(req,timeout=float(effective_timeout)) as resp:
                raw=resp.read(max_bytes+1)
        except HTTPError as exc:
            body=exc.read().decode("utf-8",errors="replace")
            raise ServiceHTTPError(f"HTTP {exc.code}: {body[:500]}") from exc
        except URLError as exc:
            raise ServiceHTTPError(f"service request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ServiceHTTPError("service request timed out") from exc
        if len(raw)>max_bytes:
            raise ServiceHTTPError("service text response exceeded max_bytes")
        return raw.decode("utf-8",errors="replace")

    def request(
        self,
        method:str,
        path:str,
        *,
        query:Mapping[str,Any]|None=None,
        payload:Any=None,
        timeout:float|None=None,
    )->Any:
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
            effective_timeout=self.timeout if timeout is None else timeout
            if (
                isinstance(effective_timeout,bool)
                or not isinstance(effective_timeout,(int,float))
                or effective_timeout<=0
            ):
                raise ValueError("timeout must be a positive number")
            with urlopen(req,timeout=float(effective_timeout)) as resp:
                raw=resp.read()
        except HTTPError as exc:
            body=exc.read().decode("utf-8",errors="replace")
            raise ServiceHTTPError(f"HTTP {exc.code}: {body[:500]}") from exc
        except URLError as exc:
            raise ServiceHTTPError(f"service request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ServiceHTTPError("service request timed out") from exc
        if not raw: return None
        try: return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:
            raise ServiceHTTPError("service returned non-JSON response") from exc
