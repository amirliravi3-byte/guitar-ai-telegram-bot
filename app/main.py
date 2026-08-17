from __future__ import annotations
import argparse, json, os, subprocess, tempfile, traceback
from pathlib import Path
from types import SimpleNamespace
from telegram_io import TelegramBot
from analyze_song import analyze_audio, format_fa
from demo_audio import render_demo
from gp5_builder import build_arrangement_gp5, build_tab_from_midi
from chord_diagram import draw_chord
from callback import fetch_job, post_state
from music_theory import normalize_chord, strumming_pattern, transpose_chord


def run(cmd):
    subprocess.run(cmd, check=True)


def convert_to_wav(src, dst):
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "22050", str(dst)])


def safe_json(value, default=None):
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value) if value else (default or {})
    except Exception:
        return default or {}


def apply_overrides(state, args):
    result = dict(state or {})
    if args.tempo_override:
        result["bpm"] = float(args.tempo_override)
    elif args.tempo_scale and result.get("bpm"):
        result["bpm"] = round(float(result["bpm"]) * float(args.tempo_scale), 1)
    if args.style:
        result["style"] = args.style
        result["strumming"] = strumming_pattern(float(result.get("bpm", 90)), result.get("meter_estimate", "4/4"), args.style)["label"]
    if args.capo_override is not None and args.capo_override >= 0:
        capo = int(args.capo_override)
        result["recommended_capo"] = capo
        chords = result.get("progression") or []
        result["play_shapes"] = [transpose_chord(c, -capo) for c in chords] if capo else list(chords)
    return result


def send_arrangement(bot, chat_id, state, outdir, prefix="arrangement"):
    chords = state.get("progression") or state.get("chords") or []
    bpm = float(state.get("bpm", 90))
    meter = state.get("meter_estimate", "4/4")
    style = state.get("style", "strum")
    mp3 = outdir / f"{prefix}_practice.mp3"
    gp5 = outdir / f"{prefix}.gp5"

    # Text should always be useful even if one artifact renderer fails.
    bot.send_message(chat_id, format_fa(state))

    render_errors = []
    try:
        render_demo(chords, bpm, meter, style, with_click=bool(state.get("with_click", False)), out_mp3=str(mp3))
        bot.send_audio(chat_id, str(mp3), "🎧 نمونه تمرینی گیتار")
    except Exception as exc:
        render_errors.append(f"MP3: {type(exc).__name__}: {str(exc)[:180]}")

    try:
        build_arrangement_gp5(chords, bpm, meter, str(gp5), style=style, capo=int(state.get("recommended_capo", 0) or 0))
        bot.send_document(chat_id, str(gp5), "🎸 فایل Guitar Pro 5")
    except Exception as exc:
        render_errors.append(f"GP5: {type(exc).__name__}: {str(exc)[:180]}")

    if render_errors:
        bot.send_message(chat_id, "⚠️ بخشی از خروجی ساخته نشد:\n" + "\n".join(render_errors))
    if len(render_errors) == 2:
        raise RuntimeError("Both MP3 and GP5 rendering failed")


def process_audio(args, bot, work):
    src = work / ("input" + Path(args.file_name or "audio.mp3").suffix)
    bot.download(args.file_id, src)
    wav = work / "analysis.wav"
    convert_to_wav(src, wav)
    result = analyze_audio(str(wav))
    result["source"] = "audio"
    result["style"] = "strum"
    send_arrangement(bot, args.chat_id, result, work, "song")
    post_state(args.chat_id, result, args.job_id, args.user_id)


def process_video(args, bot, work):
    src = work / ("input" + Path(args.file_name or "video.mp4").suffix)
    bot.download(args.file_id, src)
    wav = work / "video_audio.wav"
    convert_to_wav(src, wav)
    song_analysis = analyze_audio(str(wav))
    out_bp = work / "basic_pitch"
    out_bp.mkdir()
    run(["basic-pitch", str(out_bp), str(wav)])
    mids = list(out_bp.glob("*.mid"))
    if not mids:
        raise RuntimeError("Basic Pitch did not create MIDI.")
    midi = mids[0]
    gp5 = work / "video_transcription.gp5"
    build_tab_from_midi(str(midi), song_analysis.get("bpm", 120), str(gp5))
    text = (
        "🎥 تبدیل ویدیو به تبلچر\n"
        f"تمپو تقریبی: {song_analysis.get('bpm')} BPM\n"
        f"گام تقریبی: {song_analysis.get('key_estimate')}\n"
        "فایل GP5 و MIDI پایین ارسال شدند.\n\n"
        "ℹ️ Audio-to-MIDI روی اجرای تک‌ساز دقیق‌تر است؛ در ویدیوی دارای خواننده/درام/چند ساز، تبلچر حتماً با گوش بررسی شود."
    )
    bot.send_message(args.chat_id, text)
    bot.send_document(args.chat_id, str(gp5), "🎸 Guitar Pro transcription")
    bot.send_document(args.chat_id, str(midi), "🎹 MIDI transcription")
    state = {
        "source": "video",
        "bpm": song_analysis.get("bpm"),
        "key_estimate": song_analysis.get("key_estimate"),
        "last_gp5": "video_transcription.gp5",
    }
    post_state(args.chat_id, state, args.job_id, args.user_id)


def process_artifact(args, bot, work):
    state = safe_json(args.context_json, {})
    kind = args.artifact_type
    if kind == "chord_diagram":
        chord = normalize_chord(args.target or "E")
        png = work / f"{chord.replace('#', 'sharp')}_chord.png"
        draw_chord(chord, str(png))
        bot.send_photo(args.chat_id, str(png), f"🎸 آکورد {chord}")
        post_state(args.chat_id, state, args.job_id, args.user_id)
        return
    if kind == "chord_demo":
        chord = normalize_chord(args.target or "E")
        bpm = float(args.tempo_override or 70)
        local = {
            "progression": [chord],
            "bpm": bpm,
            "meter_estimate": "4/4",
            "key_estimate": chord,
            "strumming": strumming_pattern(bpm, "4/4", args.style or "strum")["label"],
            "style": args.style or "strum",
        }
        send_arrangement(bot, args.chat_id, local, work, f"chord_{chord.replace('#', 'sharp')}")
        post_state(args.chat_id, state, args.job_id, args.user_id)
        return
    if kind in ("arrangement", "practice_demo", "gp5"):
        if not state.get("progression"):
            raise ValueError("برای این درخواست هنوز تحلیل آهنگی در حافظه ندارم. اول MP3 بفرست.")
        state = apply_overrides(state, args)
        if args.with_click:
            state["with_click"] = True
        send_arrangement(bot, args.chat_id, state, work, "revised")
        post_state(args.chat_id, state, args.job_id, args.user_id)
        return
    raise ValueError(f"Unknown artifact type: {kind}")


def namespace_from_job(job_id: str, job: dict):
    return SimpleNamespace(
        job_id=job_id,
        job_type=str(job.get("job_type", "")),
        chat_id=str(job.get("chat_id", "")),
        user_id=str(job.get("user_id", "")),
        file_id=str(job.get("file_id", "")),
        file_name=str(job.get("file_name", "")),
        artifact_type=str(job.get("artifact_type", "")),
        target=str(job.get("target", "")),
        context_json=job.get("context_json", {}) or {},
        tempo_override=float(job.get("tempo_override") or 0),
        tempo_scale=float(job.get("tempo_scale") or 0),
        capo_override=int(job.get("capo_override")) if str(job.get("capo_override", "")).strip() not in ("", "None") else -1,
        style=str(job.get("style", "")),
        with_click=bool(job.get("with_click", False)),
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--job-id", required=True)
    cli = p.parse_args()

    job = fetch_job(cli.job_id)
    args = namespace_from_job(cli.job_id, job)
    if args.job_type not in {"audio", "video", "assistant_artifact"}:
        raise ValueError(f"Invalid job_type from n8n: {args.job_type}")
    if not args.chat_id:
        raise ValueError("Missing chat_id in job payload")

    bot = TelegramBot()
    with tempfile.TemporaryDirectory(prefix="guitar_ai_") as td:
        work = Path(td)
        try:
            if args.job_type == "audio":
                process_audio(args, bot, work)
            elif args.job_type == "video":
                process_video(args, bot, work)
            else:
                process_artifact(args, bot, work)
        except Exception as exc:
            traceback.print_exc()
            try:
                bot.send_message(args.chat_id, f"❌ پردازش کامل نشد.\n{type(exc).__name__}: {str(exc)[:700]}")
            finally:
                # Callback with the previous context makes n8n delete the queued job
                # without destroying the user's last good song context.
                try:
                    post_state(args.chat_id, safe_json(args.context_json, {}), args.job_id, args.user_id)
                except Exception:
                    pass
            raise


if __name__ == "__main__":
    main()
