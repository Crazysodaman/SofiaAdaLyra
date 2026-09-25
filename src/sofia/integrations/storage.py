"""Bounded local/NAS storage inspection and management."""
from __future__ import annotations
from pathlib import Path
from tempfile import NamedTemporaryFile
import shutil

class StorageAdapter:
    def __init__(self,roots:tuple[Path,...])->None:
        if not roots: raise ValueError("at least one storage root required")
        self.roots=tuple(root.resolve() for root in roots)

    def _root(self,index:int)->Path:
        if type(index) is not int or not 0<=index<len(self.roots):
            raise ValueError("invalid storage root index")
        root=self.roots[index]
        if not root.exists(): raise FileNotFoundError(f"storage root unavailable: {root}")
        return root

    def _path(self,index:int,relative_path:str)->Path:
        root=self._root(index)
        if not isinstance(relative_path,str): raise TypeError("relative_path must be text")
        candidate=(root/relative_path).resolve()
        try: candidate.relative_to(root)
        except ValueError as exc: raise PermissionError("storage path escapes configured root") from exc
        return candidate

    def roots_info(self)->tuple[dict[str,str|int],...]:
        return tuple({"index":i,"path":str(root)} for i,root in enumerate(self.roots))

    def usage(self)->tuple[dict[str,int|str],...]:
        out=[]
        for root in self.roots:
            usage=shutil.disk_usage(root)
            out.append({"path":str(root),"total_bytes":usage.total,"used_bytes":usage.used,"free_bytes":usage.free})
        return tuple(out)

    def list(self,root_index:int,relative_path:str=".")->tuple[dict[str,str|int|bool],...]:
        target=self._path(root_index,relative_path)
        if not target.is_dir(): raise NotADirectoryError(str(target))
        out=[]
        for item in sorted(target.iterdir(),key=lambda x:x.name.casefold()):
            stat=item.stat()
            out.append({"name":item.name,"path":str(item.relative_to(self._root(root_index))),
                        "is_dir":item.is_dir(),"size_bytes":0 if item.is_dir() else stat.st_size})
        return tuple(out)

    def read_text(self,root_index:int,relative_path:str,*,max_bytes:int=1024*1024)->str:
        target=self._path(root_index,relative_path)
        if not target.is_file(): raise FileNotFoundError(str(target))
        stat=target.stat()
        if stat.st_size>max_bytes: raise ValueError("storage text file exceeds read limit")
        return target.read_text(encoding="utf-8")

    def write_text(self,root_index:int,relative_path:str,content:str,*,overwrite:bool=False)->dict:
        target=self._path(root_index,relative_path)
        if target.exists() and not overwrite: raise FileExistsError("target exists; overwrite must be explicit")
        target.parent.mkdir(parents=True,exist_ok=True)
        with NamedTemporaryFile("w",encoding="utf-8",delete=False,dir=target.parent,prefix=target.name+".",suffix=".tmp") as fh:
            fh.write(content); temp=Path(fh.name)
        temp.replace(target)
        return {"path":str(target.relative_to(self._root(root_index))),"bytes":len(content.encode("utf-8"))}

    def mkdir(self,root_index:int,relative_path:str)->dict:
        target=self._path(root_index,relative_path)
        target.mkdir(parents=True,exist_ok=False)
        return {"path":str(target.relative_to(self._root(root_index))),"created":True}

    def copy(self,root_index:int,source:str,destination:str,*,overwrite:bool=False)->dict:
        src=self._path(root_index,source); dst=self._path(root_index,destination)
        if not src.is_file(): raise FileNotFoundError(str(src))
        if dst.exists() and not overwrite: raise FileExistsError("destination exists")
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        return {"source":source,"destination":destination,"copied":True}

    def move(self,root_index:int,source:str,destination:str,*,overwrite:bool=False)->dict:
        src=self._path(root_index,source); dst=self._path(root_index,destination)
        if not src.exists(): raise FileNotFoundError(str(src))
        if dst.exists() and not overwrite: raise FileExistsError("destination exists")
        dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():
            if dst.is_dir(): shutil.rmtree(dst)
            else: dst.unlink()
        shutil.move(str(src),str(dst))
        return {"source":source,"destination":destination,"moved":True}

    def delete(self,root_index:int,relative_path:str,*,recursive:bool=False)->dict:
        target=self._path(root_index,relative_path)
        if target==self._root(root_index): raise PermissionError("cannot delete configured storage root")
        if target.is_dir():
            if not recursive: target.rmdir()
            else: shutil.rmtree(target)
        elif target.exists(): target.unlink()
        else: raise FileNotFoundError(str(target))
        return {"path":relative_path,"deleted":True}
