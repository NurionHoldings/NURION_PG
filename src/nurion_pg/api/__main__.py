from __future__ import annotations
import uvicorn
from .settings import Settings

def main()->None:
    settings=Settings.from_env();uvicorn.run("nurion_pg.api.app:create_app",factory=True,host=settings.host,port=settings.port,log_level=settings.log_level.lower())

if __name__=="__main__":main()
