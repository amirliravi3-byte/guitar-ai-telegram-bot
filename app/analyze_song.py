from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
import librosa
from music_theory import NOTE_NAMES_SHARP, normalize_chord, recommend_capo, strumming_pattern

MAJOR_PROFILE = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88], dtype=float)
MINOR_PROFILE = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17], dtype=float)

def _cosine(a,b):
    a=np.asarray(a,float); b=np.asarray(b,float)
    na=np.linalg.norm(a); nb=np.linalg.norm(b)
    if na == 0 or nb == 0: return 0.0
    return float(np.dot(a,b)/(na*nb))

def estimate_key(chroma_mean):
    scores=[]
    for root in range(12):
        scores.append((_cosine(chroma_mean, np.roll(MAJOR_PROFILE, root)), root, "major"))
        scores.append((_cosine(chroma_mean, np.roll(MINOR_PROFILE, root)), root, "minor"))
    score, root, quality = max(scores, key=lambda x:x[0])
    name = NOTE_NAMES_SHARP[root] + ("m" if quality=="minor" else "")
    return name, round(score,3)

def _chord_templates():
    out=[]
    for r in range(12):
        for quality, intervals in (("major",(0,4,7)),("minor",(0,3,7))):
            t=np.zeros(12)
            for i in intervals: t[(r+i)%12]=1.0
            # weakly penalize non-chord tones through cosine only
            out.append((r,quality,t))
    return out
TEMPLATES=_chord_templates()

def estimate_chord(chroma_vec):
    vals=[]
    for root,quality,t in TEMPLATES:
        score=_cosine(chroma_vec,t)
        vals.append((score,root,quality))
    score,root,quality=max(vals,key=lambda x:x[0])
    name=NOTE_NAMES_SHARP[root] + ("m" if quality=="minor" else "")
    return name, float(score)

def estimate_meter(onset_env, beat_frames, bpm):
    if beat_frames is None or len(beat_frames) < 8:
        return "4/4", 0.25
    strengths = onset_env[np.clip(np.asarray(beat_frames,dtype=int),0,len(onset_env)-1)]
    strengths = (strengths - strengths.mean()) / (strengths.std()+1e-6)
    def periodic_score(n):
        groups=[[] for _ in range(n)]
        for i,v in enumerate(strengths):
            groups[i%n].append(v)
        means=np.array([np.mean(g) if g else 0 for g in groups])
        return float(means.max()-means.mean())
    s3=periodic_score(3); s4=periodic_score(4)
    if s3 > s4*1.30 and s3 > 0.25:
        # dotted-quarter pulse around 60-100 often corresponds to 6/8
        if 55 <= bpm <= 105:
            return "6/8", min(0.8, 0.4+s3/3)
        return "3/4", min(0.8, 0.4+s3/3)
    return "4/4", min(0.85, 0.45+max(0,s4)/3)

def collapse_chords(events, min_duration=0.25):
    if not events: return []
    out=[dict(events[0])]
    for ev in events[1:]:
        if ev["chord"] == out[-1]["chord"]:
            out[-1]["end"] = ev["end"]
            out[-1]["confidence"] = round((out[-1]["confidence"]+ev["confidence"])/2,3)
        else:
            out.append(dict(ev))
    return [e for e in out if e["end"]-e["start"] >= min_duration]

def analyze_audio(path: str, max_seconds: int = 360):
    y,sr=librosa.load(path, sr=22050, mono=True, duration=max_seconds)
    if y.size < sr:
        raise ValueError("Audio is too short for reliable analysis.")
    y_h=librosa.effects.harmonic(y)
    hop=512
    onset=librosa.onset.onset_strength(y=y_h, sr=sr, hop_length=hop)
    tempo, beat_frames=librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop)
    bpm=float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else 120.0
    if not math.isfinite(bpm) or bpm < 35 or bpm > 260: bpm=120.0
    chroma=librosa.feature.chroma_cqt(y=y_h, sr=sr, hop_length=hop)
    key,key_conf=estimate_key(chroma.mean(axis=1))
    meter,meter_conf=estimate_meter(onset,beat_frames,bpm)

    beat_times=list(librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)) if len(beat_frames) else []
    duration=float(librosa.get_duration(y=y,sr=sr))
    boundaries=[0.0]+beat_times+[duration]
    # remove nearly duplicate boundaries
    clean=[]
    for t in boundaries:
        if not clean or t-clean[-1] > 0.12: clean.append(float(t))
    events=[]
    for a,b in zip(clean[:-1], clean[1:]):
        fa=int(librosa.time_to_frames(a,sr=sr,hop_length=hop))
        fb=max(fa+1,int(librosa.time_to_frames(b,sr=sr,hop_length=hop)))
        vec=chroma[:,fa:min(fb,chroma.shape[1])].mean(axis=1)
        chord,conf=estimate_chord(vec)
        if conf >= 0.47:
            events.append({"start":round(a,2),"end":round(b,2),"chord":chord,"confidence":round(conf,3)})
    events=collapse_chords(events)
    progression=[]
    for ev in events:
        if not progression or progression[-1] != ev["chord"]:
            progression.append(ev["chord"])
    if len(progression)>24:
        progression=progression[:24]
    capo=recommend_capo(progression)
    pattern=strumming_pattern(bpm,meter)
    return {
        "duration_seconds": round(duration,1),
        "bpm": round(bpm,1),
        "meter_estimate": meter,
        "meter_confidence": round(float(meter_conf),2),
        "key_estimate": key,
        "key_confidence": key_conf,
        "progression": progression,
        "chord_timeline": events[:120],
        "recommended_capo": capo["capo"],
        "play_shapes": capo["shapes"],
        "strumming": pattern["label"],
        "analysis_note": "Chord/key/meter values are automatic estimates; verify by ear for performance-critical use."
    }

def format_fa(result):
    prog=" | ".join(result.get("progression",[]) or ["نامشخص"])
    shapes=" | ".join(result.get("play_shapes",[]) or [])
    capo=result.get("recommended_capo",0)
    lines=[
        "🎵 تحلیل آهنگ",
        f"گام تقریبی: {result.get('key_estimate','?')}",
        f"تمپو: {result.get('bpm','?')} BPM",
        f"میزان تقریبی: {result.get('meter_estimate','4/4')}",
        f"آکوردها: {prog}",
        f"ریتم پیشنهادی: {result.get('strumming','')}",
    ]
    if capo:
        lines += [f"کاپو پیشنهادی: فرت {capo}", f"شکل آکوردها با کاپو: {shapes}"]
    else:
        lines += ["کاپو پیشنهادی: بدون کاپو"]
    timeline = result.get("chord_timeline") or []
    if timeline:
        lines.append("\n⏱ تغییر آکوردهای تشخیص‌داده‌شده:")
        for ev in timeline[:18]:
            sec=max(0,int(round(float(ev.get("start",0)))))
            mm,ss=divmod(sec,60)
            lines.append(f"{mm:02d}:{ss:02d}  {ev.get('chord','?')}")
        if len(timeline)>18:
            lines.append("… ادامه تغییرات داخل تحلیل ذخیره شده است.")
    lines.append("\nℹ️ تشخیص آکورد/گام خودکار است و در آهنگ‌های شلوغ ممکن است نیاز به اصلاح گوش‌محور داشته باشد.")
    return "\n".join(lines)
