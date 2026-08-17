# Guitar AI Telegram Bot — n8n + GitHub Actions + Gemini

نسخه 2.0 — طراحی‌شده برای حالتی که **n8n آماده داری ولی SSH/Root سرور را نداری**.

این پروژه هیچ سرویس پردازش موسیقی را روی سرور n8n نصب نمی‌کند. n8n فقط پیام را Route می‌کند، Gemini پاسخ‌های متنی را مدیریت می‌کند و GitHub Actions پردازش فایل‌های صوتی/ویدیویی را روی Runner موقت انجام می‌دهد.

## قابلیت‌ها

### چت مربی گیتار
- آموزش آکورد، گام، ریتم، آرپژ و تئوری به فارسی
- «آکورد E رو یادم بده»
- «عکس آکورد Am رو بفرست» → PNG دیاگرام
- «آکورد G رو برام اجرا کن» → MP3 + GP5
- پیگیری مکالمه بر اساس آخرین آهنگ هر کاربر

### MP3 / Audio → Guitar accompaniment
- Key تقریبی
- BPM
- Time signature تقریبی
- Chord progression
- Timeline زمانی تغییر آکوردها
- ریتم پیشنهادی برای گیتار
- Capo پیشنهادی و شکل آکوردها
- خروجی متن
- MP3 تمرینی همان آکوردها/ریتم
- Guitar Pro 5 (`.gp5`)

بعد از تحلیل می‌توان گفت:
- «آهسته‌تر بزن»
- «روی 70 BPM بفرست»
- «آرپژش کن»
- «با مترونوم بفرست»
- «کاپو 3 بذار»
- «نسخه Guitar Pro رو دوباره بساز»

### Video → TAB / Guitar Pro
- دریافت مستقیم ویدیو از Telegram
- استخراج Audio با FFmpeg
- Audio-to-MIDI با Spotify Basic Pitch
- تبدیل MIDI به String/Fret روی گیتار استاندارد
- خروجی GP5 + MIDI + متن خلاصه

> تبلچر اتوماتیک ویدیو برای اجرای تک‌گیتار دقیق‌تر است. ویدیوهای دارای خواننده، درام و چند ساز ممکن است به اصلاح گوش‌محور نیاز داشته باشند.

## معماری

```text
Telegram Bot
   |
   v
n8n موجود روی 7host
   |
   +---- Text ----> Gemini 2.5 Flash-Lite ----> Telegram reply
   |
   +---- Audio / Video / artifact request
                 |
                 v
          n8n stores private job
                 |
           opaque job_id only
                 |
                 v
          GitHub Actions Runner
                 |
                 +--> pulls private job from n8n
                 +--> downloads file directly from Telegram
                 +--> FFmpeg / librosa / Basic Pitch / PyGuitarPro
                 +--> sends output directly to Telegram
                 +--> callback to n8n for per-user memory
```

## امنیت و حریم خصوصی

- هیچ Telegram `user_id` یا `chat_id` در کد hard-code نشده است.
- هیچ whitelist وجود ندارد؛ ربات چندکاربره است.
- Session با ترکیب `chat_id + user_id` جدا می‌شود.
- GitHub workflow فقط یک `job_id` تصادفی/opaque دریافت می‌کند.
- `chat_id`، `file_id`، متن context و اطلاعات آهنگ داخل GitHub workflow inputs عمومی ارسال نمی‌شوند.
- Bot Token، Gemini Key و Callback Secret داخل فایل‌های پروژه نیستند.
- فایل کاربر به GitHub repository یا GitHub artifact آپلود نمی‌شود؛ Runner آن را مستقیم از Telegram می‌گیرد.
- فایل‌های موقت با پایان Runner از بین می‌روند.

## محدودیت مهم Telegram

در Bot API معمولی، دانلود فایل ورودی توسط بات تا 20MB محدود است. Workflow قبل از dispatch فایل بزرگ‌تر را رد می‌کند. این محدودیت فقط با Local Bot API Server قابل افزایش است که برای آن به سرور قابل‌کنترل نیاز داریم؛ در معماری بدون SSH فعلی عمداً وارد آن نشده‌ایم.

## فایل‌های مهم

```text
.github/workflows/process-guitar.yml   GitHub Actions processor
app/main.py                            اجرای Job
app/analyze_song.py                    تحلیل BPM/Key/Chord
app/demo_audio.py                      ساخت MP3 تمرینی
app/gp5_builder.py                     ساخت GP5 و TAB
app/chord_diagram.py                   دیاگرام آکورد PNG
app/telegram_io.py                     دریافت/ارسال Telegram
app/callback.py                        Job pull + callback امن با n8n
n8n/guitar_ai_router.json              Workflow قابل Import در n8n
START_HERE_FA.md                        مراحل راه‌اندازی برای کاربر
```

## هزینه

- پروژه API پولی لازم ندارد.
- Gemini 2.5 Flash-Lite در Free Tier گوگل قابل استفاده است، مشروط به quota/دسترسی حساب.
- برای اینکه GitHub-hosted standard runners بدون مصرف دقیقه پولی اجرا شوند، Repo را **Public** بگذار. طراحی opaque-job پروژه برای همین حالت انجام شده است.
- اگر Repo را Private کنی، GitHub Free سهمیه دقیقه ماهانه دارد و پس از اتمام quota اجرا متوقف می‌شود مگر billing فعال باشد.

## نکته درباره صحت موسیقی

این سیستم یک arranger/transcriber اتوماتیک است، نه جایگزین گوش موسیقایی یا tab رسمی. Key، Chord، Meter و Video TAB همگی تخمین هستند. خروجی برای تمرین و رسیدن سریع به arrangement بسیار کاربردی است، ولی برای اجرای حرفه‌ای باید نتیجه شنیداری چک شود.
