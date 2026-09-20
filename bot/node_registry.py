"""CAP-R3-004 — Persistent Node Registry."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
VALID_SCOPES={"LOCAL","PROJECT","NETWORK","EXTERNAL_SHARE"}
class RegistryError(RuntimeError): pass
class KeyConflict(RegistryError): pass
class UnknownKey(RegistryError): pass
class InvalidRotation(RegistryError): pass
class NodeRegistryStore(ABC):
 @abstractmethod
 def register(self,node_id:str,key_id:str,public_key:str,scopes:set[str],capabilities:set[str]|None=None)->None: ...
 @abstractmethod
 def get(self,node_id:str)->dict[str,Any]|None: ...
 @abstractmethod
 def rotate(self,node_id:str,old_key_id:str,new_key_id:str,new_public_key:str)->None: ...
 @abstractmethod
 def revoke(self,node_id:str,key_id:str)->None: ...
 @abstractmethod
 def authorize(self,node_id:str,key_id:str,scope:str,capability:str|None=None)->bool: ...
 @abstractmethod
 def health(self)->dict[str,Any]: ...
class InMemoryNodeRegistry(NodeRegistryStore):
 def __init__(self): self.nodes={}
 def register(self,node_id,key_id,public_key,scopes,capabilities=None):
  scopes=set(scopes); capabilities=set(capabilities or set())
  if not scopes<=VALID_SCOPES: raise ValueError("invalid scopes")
  node=self.nodes.setdefault(node_id,{"node_id":node_id,"keys":[],"scopes":scopes,"capabilities":capabilities})
  existing=next((k for k in node["keys"] if k["key_id"]==key_id),None)
  if existing:
   if existing["public_key"]!=public_key: raise KeyConflict("REJECT_CONFLICT")
   return
  if any(k["status"]=="ACTIVE" for k in node["keys"]): raise KeyConflict("ACTIVE_KEY_EXISTS")
  node["keys"].append({"key_id":key_id,"public_key":public_key,"status":"ACTIVE"})
 def get(self,node_id):
  node=self.nodes.get(node_id); return None if node is None else {**node,"keys":[dict(k) for k in node["keys"]]}
 def rotate(self,node_id,old_key_id,new_key_id,new_public_key):
  node=self.nodes.get(node_id)
  if not node: raise UnknownKey("UNKNOWN_NODE")
  old=next((k for k in node["keys"] if k["key_id"]==old_key_id),None)
  if not old: raise UnknownKey("UNKNOWN_KEY")
  if old["status"]!="ACTIVE": raise InvalidRotation("OLD_KEY_NOT_ACTIVE")
  if any(k["key_id"]==new_key_id for k in node["keys"]): raise KeyConflict("REJECT_CONFLICT")
  old["status"]="ROTATING"; node["keys"].append({"key_id":new_key_id,"public_key":new_public_key,"status":"ACTIVE"})
 def revoke(self,node_id,key_id):
  node=self.nodes.get(node_id); key=next((k for k in node["keys"] if k["key_id"]==key_id),None) if node else None
  if not key: raise UnknownKey("UNKNOWN_KEY")
  key["status"]="REVOKED"
 def authorize(self,node_id,key_id,scope,capability=None):
  node=self.nodes.get(node_id); return bool(node and scope in node["scopes"] and (capability is None or capability in node["capabilities"]) and any(k["key_id"]==key_id and k["status"]=="ACTIVE" for k in node["keys"]))
 def health(self): return {"backend":"memory","nodes":len(self.nodes)}
class PostgreSQLNodeRegistry(NodeRegistryStore):
 def __init__(self,connection): self.connection=connection
 def register(self,node_id,key_id,public_key,scopes,capabilities=None):
  scopes=set(scopes); capabilities=set(capabilities or set())
  if not scopes<=VALID_SCOPES: raise ValueError("invalid scopes")
  with self.connection:
   with self.connection.cursor() as cur:
    cur.execute("INSERT INTO r3_nodes(node_id) VALUES(%s) ON CONFLICT(node_id) DO NOTHING",(node_id,))
    cur.execute("SELECT public_key FROM r3_node_keys WHERE node_id=%s AND key_id=%s",(node_id,key_id)); row=cur.fetchone()
    if row and row[0]!=public_key: raise KeyConflict("REJECT_CONFLICT")
    if not row: cur.execute("INSERT INTO r3_node_keys(node_id,key_id,public_key,status) VALUES(%s,%s,%s,'ACTIVE')",(node_id,key_id,public_key))
    for scope in scopes: cur.execute("INSERT INTO r3_node_scopes(node_id,scope) VALUES(%s,%s) ON CONFLICT DO NOTHING",(node_id,scope))
    for capability in capabilities: cur.execute("INSERT INTO r3_node_capabilities(node_id,capability) VALUES(%s,%s) ON CONFLICT DO NOTHING",(node_id,capability))
 def get(self,node_id):
  with self.connection.cursor() as cur:
   cur.execute("SELECT key_id,public_key,status,created_at FROM r3_node_keys WHERE node_id=%s ORDER BY created_at",(node_id,)); keys=[dict(key_id=r[0],public_key=r[1],status=r[2],created_at=r[3]) for r in cur.fetchall()]
   cur.execute("SELECT scope FROM r3_node_scopes WHERE node_id=%s",(node_id,)); scopes={r[0] for r in cur.fetchall()}
   cur.execute("SELECT capability FROM r3_node_capabilities WHERE node_id=%s",(node_id,)); caps={r[0] for r in cur.fetchall()}
  return {"node_id":node_id,"keys":keys,"scopes":scopes,"capabilities":caps} if keys else None
 def rotate(self,node_id,old_key_id,new_key_id,new_public_key):
  with self.connection:
   with self.connection.cursor() as cur:
    cur.execute("SELECT status FROM r3_node_keys WHERE node_id=%s AND key_id=%s FOR UPDATE",(node_id,old_key_id)); row=cur.fetchone()
    if row is None: raise UnknownKey("UNKNOWN_KEY")
    if row[0]!="ACTIVE": raise InvalidRotation("OLD_KEY_NOT_ACTIVE")
    cur.execute("UPDATE r3_node_keys SET status='ROTATING' WHERE node_id=%s AND key_id=%s AND status='ACTIVE'",(node_id,old_key_id))
    if getattr(cur,"rowcount",1)==0: raise InvalidRotation("OLD_KEY_NOT_ACTIVE")
    cur.execute("INSERT INTO r3_node_keys(node_id,key_id,public_key,status) VALUES(%s,%s,%s,'ACTIVE')",(node_id,new_key_id,new_public_key))
 def revoke(self,node_id,key_id):
  with self.connection:
   with self.connection.cursor() as cur:
    cur.execute("UPDATE r3_node_keys SET status='REVOKED',revoked_at=now() WHERE node_id=%s AND key_id=%s",(node_id,key_id))
    if getattr(cur,"rowcount",1)==0: raise UnknownKey("UNKNOWN_KEY")
 def authorize(self,node_id,key_id,scope,capability=None):
  if scope not in VALID_SCOPES:return False
  node=self.get(node_id); return bool(node and scope in node["scopes"] and (capability is None or capability in node["capabilities"]) and any(k["key_id"]==key_id and k["status"]=="ACTIVE" for k in node["keys"]))
 def health(self): return {"backend":"postgresql","registry":"configured_candidate"}
