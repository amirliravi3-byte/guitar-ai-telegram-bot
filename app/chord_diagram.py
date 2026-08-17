from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from music_theory import chord_shape, normalize_chord

def draw_chord(chord: str, out_path: str):
    chord=normalize_chord(chord)
    shape=chord_shape(chord)  # low E -> high e
    fretted=[f for f in shape if f>0]
    first=max(1,min(fretted) if fretted else 1)
    if first <= 3: first=1
    top=first+4
    fig,ax=plt.subplots(figsize=(5,6),dpi=180)
    ax.set_xlim(-0.8,5.8); ax.set_ylim(5.8,-1.2); ax.axis("off")
    ax.text(2.5,-0.75,chord,ha="center",va="center",fontsize=24,fontweight="bold")
    # strings high e at right? conventional diagram low E left -> high e right
    for x in range(6): ax.plot([x,x],[0,5],linewidth=1.6)
    for y in range(6): ax.plot([0,5],[y,y],linewidth=2.3 if y==0 and first==1 else 1.4)
    for i,fret in enumerate(shape):
        if fret == -1:
            ax.text(i,-0.12,"×",ha="center",va="bottom",fontsize=16)
        elif fret == 0:
            ax.text(i,-0.12,"○",ha="center",va="bottom",fontsize=16)
        else:
            y=(fret-first)+0.5
            if 0 <= y <= 4.5:
                ax.scatter([i],[y],s=280)
    if first>1:
        ax.text(-0.55,0.45,f"{first}fr",ha="center",va="center",fontsize=11)
    fig.tight_layout(pad=.5)
    fig.savefig(out_path,bbox_inches="tight")
    plt.close(fig)
    return out_path
