from __future__ import annotations
from typing import Any,Mapping

class SchemaValidationError(ValueError): pass

def validate_object(schema:Mapping[str,Any],value:Any)->None:
    if schema.get("type")!="object": return
    if not isinstance(value,dict): raise SchemaValidationError("value must be an object")
    required=schema.get("required",())
    missing=[k for k in required if k not in value]
    if missing: raise SchemaValidationError("missing required fields: "+", ".join(sorted(missing)))
    if schema.get("additionalProperties") is False:
        allowed=set(schema.get("properties",{}))
        extra=set(value)-allowed
        if extra: raise SchemaValidationError("unexpected fields: "+", ".join(sorted(extra)))
