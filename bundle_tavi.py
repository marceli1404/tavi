"""Build an allowlisted public source/model archive with exact content hashes."""
import hashlib
import json
from pathlib import Path
import zipfile
BASE=Path(__file__).resolve().parent

def main():
    files=json.loads((BASE/'release-files.json').read_text(encoding='utf-8'))
    payload={}
    for name in files:
        path=(BASE/name).resolve(strict=True)
        if not path.is_relative_to(BASE) or name.startswith(('.git/','output/','data/')):
            raise ValueError('Invalid release member')
        payload[name]=path.read_bytes()
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in payload.items()}
    payload['manifest.json']=json.dumps(manifest,indent=2).encode()
    destination=BASE/'dist/tavi-v0.15-source-and-model.zip'
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in payload.items(): archive.writestr(name,data)
    with zipfile.ZipFile(destination) as archive:
        assert set(archive.namelist())==set(payload)
        for name,digest in manifest.items(): assert hashlib.sha256(archive.read(name)).hexdigest()==digest
    print(json.dumps({'archive':str(destination),'files':len(payload),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}))

if __name__=='__main__': main()
