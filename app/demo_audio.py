from __future__ import annotations
import math, subprocess
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from music_theory import chord_pitch_classes, strumming_pattern, normalize_chord

SR=44100

def midi_to_hz(m): return 440.0 * (2 ** ((m-69)/12))

def karplus(freq, duration, rng, decay=0.996):
    n=max(2,int(SR/freq))
    total=max(1,int(duration*SR))
    buf=rng.uniform(-1,1,n).astype(np.float32)
    out=np.zeros(total,np.float32)
    for i in range(total):
        val=buf[i % n]
        nxt=0.5*(val + buf[(i+1)%n])*decay
        out[i]=val
        buf[i % n]=nxt
    # short attack / fade
    fade=min(int(.015*SR), total//4)
    if fade>0:
        out[:fade]*=np.linspace(0,1,fade)
        out[-fade:]*=np.linspace(1,0,fade)
    return out

def chord_midis(chord):
    pcs=chord_pitch_classes(chord)
    notes=[]
    # choose playable mid register, 4-5 note voicing
    for base in [40,45,50,55,59,64,67]:
        if base % 12 in pcs:
            notes.append(base)
    # fill missing chord tones
    for pc in pcs:
        candidates=[m for m in range(40,72) if m%12==pc]
        if not any(n%12==pc for n in notes) and candidates:
            notes.append(min(candidates,key=lambda m:abs(m-55)))
    notes=sorted(set(notes))
    return notes[:6]

def render_demo(chords, bpm=90, meter="4/4", style="strum", bars_per_chord=1, with_click=False, out_mp3="demo.mp3"):
    chords=[normalize_chord(c) for c in chords if c]
    if not chords: raise ValueError("No chords to render.")
    rng=np.random.default_rng(7)
    pattern=strumming_pattern(float(bpm),meter,style)
    beats_per_bar=3 if meter=="3/4" else (2 if meter=="6/8" else 4)
    sec_per_beat=60.0/float(bpm)
    bar_sec=sec_per_beat*beats_per_bar
    total=len(chords)*bars_per_chord*bar_sec + 1.5
    audio=np.zeros(int(total*SR),np.float32)

    # convert step index into bar position; 8 subdivisions for 4/4, 6 for 3/4 or 6/8
    for ci,ch in enumerate(chords):
        notes=chord_midis(ch)
        for bar in range(bars_per_chord):
            bar_start=(ci*bars_per_chord+bar)*bar_sec
            for step,direction in pattern["steps"]:
                frac=step/max(1,pattern["subdivision"])
                t=bar_start + frac*bar_sec
                ordered=notes if direction=="d" else list(reversed(notes))
                for ni,midi in enumerate(ordered):
                    start=int((t+ni*0.012)*SR)
                    pluck=karplus(midi_to_hz(midi), min(1.8,bar_sec*0.95), rng)
                    end=min(len(audio),start+len(pluck))
                    if end>start:
                        audio[start:end]+=pluck[:end-start]*(0.14 if direction=="u" else 0.18)

    if with_click:
        click_len=int(.035*SR)
        x=np.arange(click_len)/SR
        for b in np.arange(0,total,sec_per_beat):
            start=int(b*SR); end=min(len(audio),start+click_len)
            click=(np.sin(2*np.pi*1800*x[:end-start])*np.exp(-45*x[:end-start])).astype(np.float32)*0.12
            audio[start:end]+=click

    peak=float(np.max(np.abs(audio))) or 1.0
    audio=np.clip(audio/(peak*1.08),-1,1)
    wav=Path(out_mp3).with_suffix(".wav")
    wavfile.write(wav,SR,(audio*32767).astype(np.int16))
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(wav),"-codec:a","libmp3lame","-q:a","3",str(out_mp3)],check=True)
    wav.unlink(missing_ok=True)
    return str(out_mp3)
