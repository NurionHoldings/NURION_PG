"""PostgreSQL-backed authentication, key lifecycle, and access audit."""
from __future__ import annotations
from hashlib import sha256
import hmac
import json
from typing import Any
from uuid import uuid4

from nurion_pg.api.auth import Principal,Role
from .postgres import _schema


class PostgresAuthRepository:
    def __init__(self,connection:Any,schema:str="nurion_pg")->None:
        if not connection.autocommit:raise ValueError("PostgresAuthRepository requires autocommit")
        self.connection=connection;self.schema=_schema(schema)

    def authenticate(self,credential:str)->Principal|None:
        try:prefix,key_id,secret=credential.split("_",2)
        except ValueError:return None
        if prefix!="npg" or not secret:return None
        row=self.connection.execute(f"SELECT k.secret_sha256,k.active,p.principal_id,p.merchant_id,p.roles,p.status,m.status FROM {self.schema}.api_keys k JOIN {self.schema}.principals p ON p.principal_id=k.principal_id JOIN {self.schema}.merchants m ON m.merchant_id=p.merchant_id WHERE k.key_id=%s",(key_id,)).fetchone()
        expected=row[0].strip() if row else "0"*64;matches=hmac.compare_digest(sha256(secret.encode()).hexdigest(),expected)
        if not row or not matches or not row[1] or row[5]!="active" or row[6]!="active":return None
        try:roles=frozenset(Role(value) for value in row[4])
        except (TypeError,ValueError):return None
        return Principal(row[2],row[3],roles,key_id)

    def record_audit(self,principal_id:str|None,merchant_id:str|None,action:str,outcome:str,correlation_id:str)->str:
        audit_id=str(uuid4());self.connection.execute(f"INSERT INTO {self.schema}.access_audit(audit_id,principal_id,merchant_id,action,outcome,correlation_id) VALUES (%s,%s,%s,%s,%s,%s)",(audit_id,principal_id,merchant_id,action,outcome,correlation_id));return audit_id

    def rotate_key(self,principal_id:str,old_key_id:str,new_key_id:str,new_secret_sha256:str)->str:
        event_id=str(uuid4())
        with self.connection.transaction():
            updated=self.connection.execute(f"UPDATE {self.schema}.api_keys SET active=false WHERE key_id=%s AND principal_id=%s AND active=true",(old_key_id,principal_id)).rowcount
            if updated!=1:raise ValueError("active old key not found")
            self.connection.execute(f"INSERT INTO {self.schema}.api_keys(key_id,principal_id,secret_sha256) VALUES (%s,%s,%s)",(new_key_id,principal_id,new_secret_sha256))
            payload=json.dumps({"principal_id":principal_id,"old_key_id":old_key_id,"new_key_id":new_key_id})
            self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'principal',%s,'api_key.rotated',%s::jsonb)",(event_id,principal_id,payload))
        return event_id

    def revoke_key(self,principal_id:str,key_id:str)->bool:
        with self.connection.transaction():
            updated=self.connection.execute(f"UPDATE {self.schema}.api_keys SET active=false WHERE key_id=%s AND principal_id=%s AND active=true",(key_id,principal_id)).rowcount
        return updated==1
