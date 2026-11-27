#!/usr/bin/env python3
"""Read-only reference retrieval and local REA adapter invocation. Never authorizes production."""
import argparse, hashlib, json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def select(root, genre=None, ids=None, related=False):
    refs = read_json(root/'reference_registry.json')['references']
    byid = {r['id']: r for r in refs}
    if len(byid)!=len(refs): raise ValueError('duplicate reference ID')
    genres = read_json(root/'genre_registry.json')
    if not ids:
        g = (genre or '').strip().lower()
        g = genres['aliases'].get(g,g)
        ids = genres['defaults'].get(g) or (genres['related_candidates'].get(g) if related else None)
        if not ids: raise ValueError(f'NO_MATCH: {g}; use explicit --id or existing genre profile')
    return [byid[i] for i in dict.fromkeys(ids)]

def safe_path(root, relative):
    root=root.resolve(); p=Path(relative)
    if p.is_absolute() or '..' in p.parts: raise ValueError('unsafe registry path')
    target=(root/p).resolve()
    if not target.is_relative_to(root): raise ValueError('unsafe resolved path')
    return target

def get_video(root, entry, hydrate=False):
    rel=entry['path']; p=safe_path(root,rel)
    if not re.fullmatch(r'references/[A-Za-z0-9_/-]+/original\.mp4',rel): raise ValueError('invalid video path')
    if not re.fullmatch(r'[0-9a-f]{64}',entry['sha256']): raise ValueError('invalid sha256')
    pointer=False
    if p.is_file():
        with p.open('rb') as f: pointer=f.read(42).startswith(b'version https://git-lfs.github.com/spec/v1')
    if (not p.is_file() or pointer) and hydrate:
        gitroot=Path(subprocess.check_output(['git','-C',str(root),'rev-parse','--show-toplevel'],text=True,timeout=30).strip()).resolve()
        repo_rel=p.relative_to(gitroot).as_posix()
        subprocess.run(['git','-C',str(gitroot),'lfs','pull','--include='+repo_rel,'--exclude='],check=True,timeout=300)
    if not p.is_file(): raise FileNotFoundError('MEDIA_MISSING: '+entry['id']+' '+str(p))
    if p.stat().st_size!=entry['bytes'] or sha(p)!=entry['sha256']: raise ValueError('INTEGRITY_FAILED: '+entry['id']+' (missing/corrupt/LFS pointer)')
    return p

def analyzer_fingerprint(studio):
    h=hashlib.sha256()
    files=[studio/'scripts/rea_analyze.py', studio/'requirements.lock',studio/'pyproject.toml']
    files+=sorted((studio/'intelligence').glob('*.py'))
    for p in files:
        if p.is_file(): h.update(str(p.relative_to(studio)).encode()+b'\0'+sha(p).encode()+b'\0')
    if not (studio/'scripts/rea_analyze.py').is_file(): raise FileNotFoundError('studio REA script missing')
    return h.hexdigest()

def analyze(studio, video, entry, out_root, threshold=.30):
    if not 0<threshold<1: raise ValueError('invalid threshold')
    out_root.mkdir(parents=True,exist_ok=True)
    dest=Path(tempfile.mkdtemp(prefix=entry['id']+'-',dir=out_root))
    fingerprint=analyzer_fingerprint(studio)
    cmd=[sys.executable,str(studio/'scripts/rea_analyze.py'),str(video),'--out',str(dest),'--threshold',str(threshold)]
    subprocess.run(cmd,cwd=studio,check=True,timeout=1800)
    report=dest/'reference_analysis.json'
    data=read_json(report)
    if not data.get('measurements') or not isinstance(data.get('ffmpeg_scene_candidates'),list): raise ValueError('invalid REA report')
    result={'reference_id':entry['id'],'video_sha256':entry['sha256'],'analyzer_fingerprint':fingerprint,'threshold':threshold,'report_sha256':sha(report),'report_path':str(report),'status':'BASELINE_ANALYSIS_COMPLETE_REQUIRES_VISUAL_REVIEW','production_authorized':False}
    (dest/'retrieval_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['list','verify','resolve','analyze']); p.add_argument('--database',type=Path,default=ROOT); p.add_argument('--genre'); p.add_argument('--id',action='append'); p.add_argument('--include-related',action='store_true'); p.add_argument('--hydrate',action='store_true'); p.add_argument('--studio',type=Path); p.add_argument('--out',type=Path,default=ROOT/'.rea-output'); p.add_argument('--threshold',type=float,default=.30)
    a=p.parse_args(); root=a.database.resolve()
    if a.action=='list': print(json.dumps(read_json(root/'reference_registry.json'),indent=2)); return
    refs=read_json(root/'reference_registry.json')['references'] if a.action=='verify' and not a.genre and not a.id else select(root,a.genre,a.id,a.include_related)
    results=[]
    for r in refs:
        v=get_video(root,r,a.hydrate)
        if a.action=='analyze':
            if not a.studio: p.error('--studio required for analyze')
            results.append(analyze(a.studio.resolve(),v,r,a.out.resolve(),a.threshold))
        else: results.append({'id':r['id'],'path':str(v),'sha256':r['sha256'],'status':'VERIFIED','production_authorized':False})
    print(json.dumps(results,indent=2))

if __name__=='__main__': main()
