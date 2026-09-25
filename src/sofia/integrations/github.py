"""GitHub REST adapter for repository inspection and bounded issue creation."""
from __future__ import annotations
from urllib.parse import quote
from typing import Any
from .http import JsonHttpClient

class GitHubAdapter:
    def __init__(self,repository:str,token:str|None=None,base_url:str="https://api.github.com")->None:
        if repository.count("/")!=1: raise ValueError("repository must be owner/name")
        headers={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
        if token:
            headers["Authorization"]=f"Bearer {token}"
        self.repository=repository; self.http=JsonHttpClient(base_url,headers=headers)
    def repository_info(self)->dict[str,Any]:
        data=self.http.request("GET",f"/repos/{self.repository}")
        if not isinstance(data,dict): raise RuntimeError("invalid GitHub repository response")
        return data
    def issues(self,*,state:str="open",limit:int=30)->list[dict[str,Any]]:
        if state not in ("open","closed","all"): raise ValueError("invalid issue state")
        if not 1<=limit<=100: raise ValueError("limit must be 1..100")
        data=self.http.request("GET",f"/repos/{self.repository}/issues",query={"state":state,"per_page":limit})
        if not isinstance(data,list): raise RuntimeError("invalid GitHub issues response")
        return data
    def file(self,path:str,*,ref:str|None=None)->dict[str,Any]:
        if not path.strip() or path.startswith("/") or ".." in path.split("/"): raise ValueError("invalid repository path")
        data=self.http.request("GET",f"/repos/{self.repository}/contents/{quote(path,safe='/')}",query={"ref":ref})
        if not isinstance(data,dict): raise RuntimeError("invalid GitHub content response")
        return data
    def create_issue(self,title:str,body:str="")->dict[str,Any]:
        if not title.strip(): raise ValueError("issue title required")
        data=self.http.request("POST",f"/repos/{self.repository}/issues",payload={"title":title,"body":body})
        if not isinstance(data,dict): raise RuntimeError("invalid GitHub create-issue response")
        return data
