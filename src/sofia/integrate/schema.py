"""Small dependency-free JSON-schema subset used at adapter boundaries."""
from __future__ import annotations
from typing import Any,Mapping

class SchemaValidationError(ValueError): pass

def _fail(path:str,message:str)->None:
    raise SchemaValidationError(f"{path}: {message}")

def validate_object(schema:Mapping[str,Any],value:Any,*,path:str="$")->None:
    if not isinstance(schema,Mapping): _fail(path,"schema must be an object")
    if "enum" in schema and value not in schema["enum"]: _fail(path,"value is not in enum")
    kind=schema.get("type")
    if kind is None:
        return
    if kind=="object":
        if not isinstance(value,dict): _fail(path,"value must be an object")
        required=schema.get("required",())
        missing=[k for k in required if k not in value]
        if missing: _fail(path,"missing required fields: "+", ".join(sorted(missing)))
        properties=schema.get("properties",{})
        if schema.get("additionalProperties") is False:
            extra=set(value)-set(properties)
            if extra: _fail(path,"unexpected fields: "+", ".join(sorted(extra)))
        for key,subschema in properties.items():
            if key in value: validate_object(subschema,value[key],path=f"{path}.{key}")
        return
    if kind=="array":
        if not isinstance(value,list): _fail(path,"value must be an array")
        if "minItems" in schema and len(value)<schema["minItems"]: _fail(path,"array shorter than minItems")
        if "maxItems" in schema and len(value)>schema["maxItems"]: _fail(path,"array longer than maxItems")
        item_schema=schema.get("items")
        if item_schema is not None:
            for index,item in enumerate(value): validate_object(item_schema,item,path=f"{path}[{index}]")
        return
    if kind=="string":
        if not isinstance(value,str): _fail(path,"value must be a string")
        if "minLength" in schema and len(value)<schema["minLength"]: _fail(path,"string shorter than minLength")
        if "maxLength" in schema and len(value)>schema["maxLength"]: _fail(path,"string longer than maxLength")
        return
    if kind=="integer":
        if type(value) is not int: _fail(path,"value must be an integer")
    elif kind=="number":
        if type(value) not in (int,float): _fail(path,"value must be a number")
    elif kind=="boolean":
        if type(value) is not bool: _fail(path,"value must be a boolean")
    elif kind=="null":
        if value is not None: _fail(path,"value must be null")
    else:
        _fail(path,f"unsupported schema type: {kind}")
    if kind in ("integer","number"):
        if "minimum" in schema and value<schema["minimum"]: _fail(path,"value below minimum")
        if "maximum" in schema and value>schema["maximum"]: _fail(path,"value above maximum")
