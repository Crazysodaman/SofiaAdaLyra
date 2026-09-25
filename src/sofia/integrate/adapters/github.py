"""GitHub repository REST adapter with bounded repository-scoped operations."""
from __future__ import annotations
from datetime import datetime,timezone
from re import fullmatch
from sofia.external.adapter import ExternalIntegrationAdapter
from sofia.external.model import ExternalObservationState,ExternalSystem,ExternalSystemAction,ExternalSystemObservation,ExternalSystemResult,ExternalSystemResultKind,ExternalSystemType
from sofia.integrate.http import JsonHttpClient,UrllibJsonHttpClient

_REPO_PART=r"[A-Za-z0-9_.-]+"

class GitHubRepositoryAdapter(ExternalIntegrationAdapter):
    def __init__(self,owner:str,repository:str,token:str|None=None,*,http:JsonHttpClient|None=None,api_url:str="https://api.github.com")->None:
        if fullmatch(_REPO_PART,owner) is None or fullmatch(_REPO_PART,repository) is None: raise ValueError("invalid GitHub repository identity")
        self.owner=owner; self.repository=repository; self._token=token; self._http=http or UrllibJsonHttpClient(); self._api_url=api_url.rstrip("/")
        self._system=ExternalSystem(f"github:{owner}/{repository}",f"GitHub {owner}/{repository}",ExternalSystemType.PLATFORM,"GitHub repository")
    @property
    def name(self)->str: return "github-rest"
    @property
    def system(self)->ExternalSystem: return self._system
    @property
    def _headers(self)->dict[str,str]:
        headers={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2026-03-10"}
        if self._token: headers["Authorization"]=f"Bearer {self._token}"
        return headers
    @property
    def _repo_path(self)->str: return f"/repos/{self.owner}/{self.repository}"
    def observe(self)->ExternalSystemObservation:
        repo=self._http.request("GET",f"{self._api_url}{self._repo_path}",headers=self._headers)
        prs=self._http.request("GET",f"{self._api_url}{self._repo_path}/pulls?state=open&per_page=100",headers=self._headers)
        open_prs=prs.payload if isinstance(prs.payload,list) else []
        repository=repo.payload if isinstance(repo.payload,dict) else {"raw":repo.payload}
        return ExternalSystemObservation(self.system,datetime.now(timezone.utc),ExternalObservationState.VERIFIED,
            {"repository":repository,"open_pull_request_count":len(open_prs),"open_pull_requests":open_prs},self.name)
    def execute_action(self,action:ExternalSystemAction)->ExternalSystemResult:
        if action.system_id!=self.system.system_id: raise ValueError("action targets a different repository")
        if action.action_name!="create_issue": raise ValueError("unsupported GitHub action")
        title=action.parameters.get("title"); body=action.parameters.get("body","")
        if not isinstance(title,str) or not title.strip(): raise ValueError("GitHub issue title is required")
        if not isinstance(body,str): raise TypeError("GitHub issue body must be a string")
        response=self._http.request("POST",f"{self._api_url}{self._repo_path}/issues",headers=self._headers,payload={"title":title,"body":body})
        return ExternalSystemResult(self.system.system_id,ExternalSystemResultKind.SUCCESS,
            {"status":response.status,"issue":response.payload},datetime.now(timezone.utc),self.name)
