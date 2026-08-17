from app.music_theory import normalize_chord, transpose_chord, recommend_capo, strumming_pattern

def test_normalize():
    assert normalize_chord("Bb")=="A#"
    assert normalize_chord("F#m7")=="F#m"

def test_transpose():
    assert transpose_chord("E",-2)=="D"
    assert transpose_chord("Am",3)=="Cm"

def test_capo():
    r=recommend_capo(["F","Bb","C"])
    assert 0 <= r["capo"] <= 6
    assert len(r["shapes"])==3

def test_strum():
    assert "label" in strumming_pattern(90,"4/4")
