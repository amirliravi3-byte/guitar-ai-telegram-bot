from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterable

NOTE_NAMES_SHARP = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
FLAT_TO_SHARP = {"Db":"C#","Eb":"D#","Gb":"F#","Ab":"G#","Bb":"A#"}

# low-E -> high-e; -1 = mute
COMMON_SHAPES = {
    "C":  [-1,3,2,0,1,0],
    "Cm": [-1,3,5,5,4,3],
    "C#": [-1,4,6,6,6,4],
    "C#m":[-1,4,6,6,5,4],
    "D":  [-1,-1,0,2,3,2],
    "Dm": [-1,-1,0,2,3,1],
    "D#": [-1,6,8,8,8,6],
    "D#m":[-1,6,8,8,7,6],
    "E":  [0,2,2,1,0,0],
    "Em": [0,2,2,0,0,0],
    "F":  [1,3,3,2,1,1],
    "Fm": [1,3,3,1,1,1],
    "F#": [2,4,4,3,2,2],
    "F#m":[2,4,4,2,2,2],
    "G":  [3,2,0,0,0,3],
    "Gm": [3,5,5,3,3,3],
    "G#": [4,6,6,5,4,4],
    "G#m":[4,6,6,4,4,4],
    "A":  [-1,0,2,2,2,0],
    "Am": [-1,0,2,2,1,0],
    "A#": [-1,1,3,3,3,1],
    "A#m":[-1,1,3,3,2,1],
    "B":  [-1,2,4,4,4,2],
    "Bm": [-1,2,4,4,3,2],
}
EASY_SHAPES = {"C","D","Dm","E","Em","G","A","Am"}

def normalize_chord(chord: str) -> str:
    s = chord.strip().replace("♭","b").replace("♯","#")
    m = re.match(r"^([A-Ga-g])([#b]?)(.*)$", s)
    if not m:
        return s
    root = m.group(1).upper() + m.group(2)
    root = FLAT_TO_SHARP.get(root, root)
    suffix = m.group(3)
    # keep major/minor triad semantics for arranger
    minor = suffix.startswith("m") and not suffix.startswith("maj")
    return root + ("m" if minor else "")

def chord_root_quality(chord: str):
    c = normalize_chord(chord)
    minor = c.endswith("m")
    root = c[:-1] if minor else c
    return root, "minor" if minor else "major"

def transpose_chord(chord: str, semitones: int) -> str:
    root, quality = chord_root_quality(chord)
    idx = NOTE_NAMES_SHARP.index(root)
    new_root = NOTE_NAMES_SHARP[(idx + semitones) % 12]
    return new_root + ("m" if quality == "minor" else "")

def chord_pitch_classes(chord: str) -> list[int]:
    root, quality = chord_root_quality(chord)
    r = NOTE_NAMES_SHARP.index(root)
    intervals = [0,3,7] if quality == "minor" else [0,4,7]
    return [(r+i) % 12 for i in intervals]

def chord_shape(chord: str) -> list[int]:
    c = normalize_chord(chord)
    if c in COMMON_SHAPES:
        return list(COMMON_SHAPES[c])
    # fallback movable E/Em shape
    root, quality = chord_root_quality(c)
    r = NOTE_NAMES_SHARP.index(root)
    e = NOTE_NAMES_SHARP.index("E")
    fret = (r - e) % 12
    if fret == 0:
        return COMMON_SHAPES["Em" if quality=="minor" else "E"]
    base = [0,2,2,0 if quality=="minor" else 1,0,0]
    return [x+fret if x >= 0 else -1 for x in base]

def difficulty(chord: str) -> float:
    c = normalize_chord(chord)
    if c in EASY_SHAPES:
        return 0
    sh = chord_shape(c)
    sounding = [x for x in sh if x >= 0]
    if not sounding:
        return 9
    spread = max(sounding) - min(sounding)
    barre_like = sum(1 for x in sounding if x == min(v for v in sounding if v > 0)) >= 3 if any(v>0 for v in sounding) else False
    return 2.5 + 0.5*spread + (1.5 if barre_like else 0)

def recommend_capo(chords: Iterable[str], max_capo: int = 6) -> dict:
    src = [normalize_chord(c) for c in chords if c]
    if not src:
        return {"capo": 0, "shapes": [], "score": 0}
    best = None
    for capo in range(max_capo+1):
        shapes = [transpose_chord(c, -capo) for c in src]
        score = sum(difficulty(c) for c in shapes) + capo * 0.12
        candidate = {"capo": capo, "shapes": shapes, "score": round(score,2)}
        if best is None or score < best["score"]:
            best = candidate
    return best

def strumming_pattern(bpm: float, meter: str = "4/4", style: str = "strum"):
    if style == "arpeggio":
        if meter in ("3/4","6/8"):
            return {"label":"Bass–3–2–1–2–3", "steps":[(0,"d"),(1,"u"),(2,"u"),(3,"u"),(4,"u"),(5,"u")], "subdivision":6}
        return {"label":"Bass–3–2–1–2–3–2–1", "steps":[(0,"d"),(1,"u"),(2,"u"),(3,"u"),(4,"u"),(5,"u"),(6,"u"),(7,"u")], "subdivision":8}
    if meter == "3/4":
        return {"label":"↓  ↓↑  ↓↑", "steps":[(0,"d"),(2,"d"),(3,"u"),(4,"d"),(5,"u")], "subdivision":6}
    if meter == "6/8":
        return {"label":"↓ · ↓↑ · ↑↓↑", "steps":[(0,"d"),(2,"d"),(3,"u"),(5,"u")], "subdivision":6}
    if bpm < 75:
        return {"label":"↓  ↓↑  ↑↓↑", "steps":[(0,"d"),(2,"d"),(3,"u"),(5,"u"),(6,"d"),(7,"u")], "subdivision":8}
    if bpm < 125:
        return {"label":"↓ ↓↑ ↑↓↑", "steps":[(0,"d"),(2,"d"),(3,"u"),(5,"u"),(6,"d"),(7,"u")], "subdivision":8}
    return {"label":"↓↑ ↓↑ ↓↑ ↓↑", "steps":[(0,"d"),(1,"u"),(2,"d"),(3,"u"),(4,"d"),(5,"u"),(6,"d"),(7,"u")], "subdivision":8}
