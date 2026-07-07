#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, json, os, re, time, platform
from pathlib import Path
VIDEO_EXTS={'.mp4','.mov','.mkv','.m4v'}
MARGINS={'louvor':(12,18),'pregacao':(8,10),'apelo':(15,20),'oracao':(12,15),'ministracao':(15,20),'frase_forte':(8,10),'avisos':(5,6)}
LABELS={'louvor':'Louvor','pregacao':'Pregação','apelo':'Apelo','oracao':'Oração','ministracao':'Ministração','frase_forte':'Frase forte','avisos':'Avisos'}
COLORS={'louvor':'Blue','pregacao':'Yellow','apelo':'Red','oracao':'Purple','ministracao':'Orange','frase_forte':'Green','avisos':'Gray'}
def norm(s):
    s=str(s or '').lower(); return s.translate(str.maketrans('áàãâäéèêëíìîïóòõôöúùûüç','aaaaaeeeeiiiiooooouuuuc'))
def safe_name(s,limit=90):
    s=re.sub(r'\s+',' ',str(s or '')).strip(); s=re.sub(r'[\\/:*?"<>|]+','-',s).strip(' .-_'); return (s[:limit].strip(' .-_') or 'FrameZero')
def tc(seconds,fps=30):
    seconds=max(0.0,float(seconds or 0)); total=int(round(seconds*fps)); hh=total//(fps*3600); total%=fps*3600; mm=total//(fps*60); total%=fps*60; ss=total//fps; ff=total%fps; return f'{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}'
def xml_escape(s): return str(s or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
def obs_recording_dirs():
    dirs=[]; home=Path.home(); roots=[]; sysname=platform.system().lower()
    if sysname=='darwin': roots.append(home/'Library/Application Support/obs-studio/basic/profiles')
    elif sysname.startswith('win') and os.environ.get('APPDATA'): roots.append(Path(os.environ['APPDATA'])/'obs-studio/basic/profiles')
    for root in roots:
        if not root.exists(): continue
        for ini in root.glob('*/basic.ini'):
            try:
                txt=ini.read_text(encoding='utf-8',errors='ignore')
                for m in re.finditer(r'(?im)^\s*(RecFilePath|FilePath)\s*=\s*(.+?)\s*$',txt):
                    raw=m.group(2).strip().strip('"')
                    if raw:
                        raw=raw.replace('%USERPROFILE%',str(home)); p=Path(os.path.expandvars(os.path.expanduser(raw)))
                        if p.exists() and p.is_dir(): dirs.append(p)
            except Exception: pass
    seen=set(); out=[]
    for d in dirs:
        key=str(d.resolve())
        if key not in seen: seen.add(key); out.append(d)
    return out
def recent_recording():
    cand=[]; now=time.time()
    for d in obs_recording_dirs():
        try:
            for p in d.iterdir():
                try:
                    if not p.is_file() or p.suffix.lower() not in VIDEO_EXTS: continue
                    st=p.stat(); low=str(p).lower()
                    if st.st_size<5*1024*1024 or now-st.st_mtime>36*3600: continue
                    if 'framezero' in low and ('corte' in low or 'clip' in low): continue
                    cand.append((st.st_mtime,st.st_size,p))
                except Exception: pass
        except Exception: pass
    if not cand: return ''
    cand.sort(key=lambda x:(x[0],x[1]),reverse=True); return str(cand[0][2])
def metadata_dirs(recording,cuts_arg=''):
    dirs=[]
    if cuts_arg:
        p=Path(os.path.expanduser(cuts_arg))
        if p.exists(): dirs.append(p)
    bases=[]
    if recording: bases.append(recording.parent)
    bases += [Path.home()/'Movies',Path.home()/'Videos',Path.home()/'Desktop',Path.home()/'Documents']
    for base in bases:
        try:
            if not base.exists(): continue
            for pattern in ('*FrameZero*','*Cortes*','*cortes*'):
                for p in base.glob(pattern):
                    if p.is_dir(): dirs.append(p)
        except Exception: pass
    seen=set(); out=[]
    for d in dirs:
        try: key=str(d.resolve())
        except Exception: key=str(d)
        if key not in seen: seen.add(key); out.append(d)
    return out
def category(meta):
    blob=' '.join(str(meta.get(k,'') or '') for k in ('titulo','texto','texto_final_corte','emocao','funcao','razao','origem')); b=norm(blob)
    if any(x in b for x in ['louvor','adoracao','music','worship','canto','melodia','congregacional']): return 'louvor'
    if any(x in b for x in ['apelo','salvacao','aceitar jesus','chamado','altar']): return 'apelo'
    if any(x in b for x in ['oracao','orar','intercess','clamor']): return 'oracao'
    if any(x in b for x in ['ministracao','fundo musical','profet','imposicao']): return 'ministracao'
    if any(x in b for x in ['aviso','agenda','inscricao','oferta','dizimo']): return 'avisos'
    if any(x in b for x in ['pregacao','sermao','biblia','versiculo']): return 'pregacao'
    try:
        if int(float(meta.get('score',0) or 0))>=85: return 'frase_forte'
    except Exception: pass
    return 'pregacao'
def load_events(recording,cuts_arg=''):
    metas=[]; now=time.time()
    for d in metadata_dirs(recording,cuts_arg):
        try:
            for mp in d.glob('**/metadata.json'):
                try:
                    if now-mp.stat().st_mtime>14*24*3600: continue
                    m=json.loads(mp.read_text(encoding='utf-8')); m['_metadata_path']=str(mp); metas.append(m)
                except Exception: pass
        except Exception: pass
    events=[]
    for i,m in enumerate(metas,1):
        cat=category(m); before,after=MARGINS.get(cat,(8,10))
        try: score=int(float(m.get('score',0) or 0))
        except Exception: score=0
        title=safe_name(m.get('titulo') or m.get('title') or LABELS.get(cat,'Momento'),70)
        try:
            if m.get('inicio_exato') is not None and m.get('fim_exato') is not None:
                start=float(m.get('inicio_exato') or 0); end=float(m.get('fim_exato') or 0)
            else:
                peak=float(m.get('tempo',0) or 0); start=max(0.0,peak-before); end=max(start+2.0,peak+after)
        except Exception: continue
        if end<=start: end=start+10
        events.append({'idx':i,'cat':cat,'label':LABELS.get(cat,'Momento'),'color':COLORS.get(cat,'Blue'),'title':title,'start':round(start,3),'end':round(end,3),'dur':round(max(1.0,end-start),3),'score':score,'metadata':m.get('_metadata_path','')})
    events.sort(key=lambda e:(-e['score'],e['start'])); chosen=[]
    for ev in events:
        if any(abs(ev['start']-x['start'])<4 and ev['title']==x['title'] for x in chosen): continue
        chosen.append(ev)
    chosen.sort(key=lambda e:e['start'])
    for n,ev in enumerate(chosen,1): ev['idx']=n
    return chosen
def write_edl(path,events,recording,fps=30):
    lines=['TITLE: FRAMEZERO_TIMELINE','FCM: NON-DROP FRAME','']; dst=0.0
    for n,ev in enumerate(events,1):
        src_in,src_out=ev['start'],ev['end']; dst_in,dst_out=dst,dst+ev['dur']
        lines.append(f"{n:03d}  AX       V     C        {tc(src_in,fps)} {tc(src_out,fps)} {tc(dst_in,fps)} {tc(dst_out,fps)}")
        lines.append(f"* FROM CLIP NAME: {recording.name}")
        lines.append(f"* COMMENT: {ev['label']} | {ev['title']} | Score {ev['score']} | Color {ev['color']}")
        lines.append(''); dst=dst_out
    path.write_text('\n'.join(lines),encoding='utf-8')
def write_fcpxml(path,events,recording):
    src=recording.expanduser().resolve().as_uri(); total=sum(e['dur'] for e in events) or 1; out=[]
    out += ['<?xml version="1.0" encoding="UTF-8"?>','<!DOCTYPE fcpxml>','<fcpxml version="1.10">','  <resources>','    <format id="r1" name="FFVideoFormat1080p30" frameDuration="100/3000s" width="1920" height="1080"/>']
    out.append(f'    <asset id="r2" name="{xml_escape(recording.name)}" src="{xml_escape(src)}" start="0s" duration="86400s" hasVideo="1" hasAudio="1"/>')
    out.append('  </resources>')
    out.append('  <library><event name="FrameZero"><project name="FRAMEZERO_TIMELINE"><sequence format="r1" duration="'+f'{total:.3f}'+'s" tcStart="0s" tcFormat="NDF"><spine>')
    dst=0.0
    for ev in events:
        name=f"{ev['label']} - {ev['title']} - Score {ev['score']}"
        out.append(f'    <asset-clip name="{xml_escape(name)}" ref="r2" offset="{dst:.3f}s" start="{ev["start"]:.3f}s" duration="{ev["dur"]:.3f}s">')
        out.append(f'      <marker start="0s" value="{xml_escape(ev["color"] + " - " + name)}" completed="0"/>')
        out.append('    </asset-clip>'); dst += ev['dur']
    out += ['  </spine></sequence></project></event></library>','</fcpxml>']
    path.write_text('\n'.join(out),encoding='utf-8')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--recording',default=''); ap.add_argument('--cuts',default=''); ap.add_argument('--fps',default=30,type=int); args=ap.parse_args()
    rec=args.recording or recent_recording()
    if not rec: raise SystemExit('ERRO: não achei gravação original. Use --recording "/caminho/video.mp4"')
    recording=Path(os.path.expanduser(rec))
    if not recording.exists(): raise SystemExit(f'ERRO: gravação não existe: {recording}')
    events=load_events(recording,args.cuts)
    if not events: raise SystemExit('ERRO: não achei metadata.json dos cortes. Use --cuts "/pasta/FrameZero_Cortes..."')
    outdir=recording.parent/'TIMELINE_EDITOR'; outdir.mkdir(parents=True,exist_ok=True); stem=safe_name(recording.stem,90)
    edl=outdir/f'{stem}_FRAMEZERO_TIMELINE.edl'; fcpxml=outdir/f'{stem}_FRAMEZERO_TIMELINE.fcpxml'
    write_edl(edl,events,recording,fps=args.fps); write_fcpxml(fcpxml,events,recording)
    info=outdir/f'{stem}_FRAMEZERO_TIMELINE_INFO.json'; info.write_text(json.dumps({'recording':str(recording),'events':len(events),'edl':str(edl),'fcpxml':str(fcpxml),'margins':MARGINS,'categories':LABELS},ensure_ascii=False,indent=2),encoding='utf-8')
    print('OK: timeline exportada'); print('EDL:',edl); print('FCPXML:',fcpxml); print('Eventos:',len(events))
if __name__=='__main__': main()
