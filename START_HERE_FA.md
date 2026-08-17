# از اینجا شروع کن — بدون SSH

برای راه‌اندازی، لازم نیست به VPS یا ترمینال دسترسی داشته باشی. فقط سه پنل لازم است:

1. GitHub
2. n8n فعلی تو
3. Google AI Studio برای Gemini API Key

---

## مرحله 1 — GitHub Repository

یک Repository با این نام بساز:

`guitar-ai-telegram-bot`

برای نسخه کاملاً بدون هزینه Runner، Visibility را **Public** قرار بده.

بعد فایل‌های این پکیج را داخل repo قرار بده. مهم است پوشه زیر دقیقاً وجود داشته باشد:

`.github/workflows/process-guitar.yml`

> هیچ Token یا API Key را داخل فایل‌های repo نگذار.

### GitHub Secrets

در Repository برو به:

`Settings → Secrets and variables → Actions → New repository secret`

چهار Secret بساز:

### 1. TELEGRAM_BOT_TOKEN
Value: Token همان Telegram Bot فعلی تو.

### 2. N8N_JOB_URL
Value:

`https://96844.7host.cloud/webhook/guitar-ai-job-v2`

### 3. N8N_CALLBACK_URL
Value:

`https://96844.7host.cloud/webhook/guitar-ai-state-v2`

### 4. N8N_CALLBACK_SECRET
یک رمز تصادفی قوی بساز؛ مثلاً حداقل 32 کاراکتر. این مقدار باید دقیقاً همان مقداری باشد که بعداً در Header Auth داخل n8n قرار می‌دهی.

---

## مرحله 2 — GitHub Fine-grained PAT برای n8n

در GitHub یک Fine-grained Personal Access Token بساز.

Repository access:

`Only select repositories → guitar-ai-telegram-bot`

Repository permissions:

`Actions: Read and write`

Token را Copy کن و جای امن نگه دار. آن را داخل repo یا Workflow JSON ننویس.

---

## مرحله 3 — Gemini API Key

در Google AI Studio یک Gemini API Key بساز.

Workflow از مدل:

`gemini-2.5-flash-lite`

استفاده می‌کند.

---

## مرحله 4 — Import در n8n

در n8n فعلی:

`Workflows → Import from File`

فایل زیر را Import کن:

`n8n/guitar_ai_router.json`

### A) Telegram Credential

روی این Nodeها Credential همان ربات فعلی را انتخاب کن:

- Telegram Trigger
- Send AI Reply
- Ack Artifact
- Ack File
- Send Input Error

### B) Gemini Header Auth

یک Credential از نوع Header Auth بساز:

Name:
`x-goog-api-key`

Value:
`GEMINI_API_KEY خودت`

بعد روی Node **Gemini Guitar Teacher** انتخابش کن.

### C) GitHub Bearer Auth

یک Credential از نوع Bearer Auth بساز و Fine-grained PAT مرحله 2 را داخلش قرار بده.

روی هر دو Node زیر انتخابش کن:

- GitHub Dispatch File
- GitHub Dispatch Artifact

### D) n8n Webhook Secret

یک Credential از نوع Header Auth بساز:

Name:
`X-Guitar-AI-Secret`

Value:
`همان N8N_CALLBACK_SECRET که در GitHub Secrets گذاشتی`

این Credential را روی هر دو Node انتخاب کن:

- GitHub Job Pull
- GitHub State Callback

### E) Project Config

Node **Project Config** را باز کن.

این مقدار را:

`github_owner:"CHANGE_ME"`

به username واقعی GitHub خودت تغییر بده.

اگر اسم repo را عوض نکرده‌ای، این را دست نزن:

`github_repo:"guitar-ai-telegram-bot"`

---

## مرحله 5 — Activate

Workflow را Save و **Activate** کن.

Production webhookها بعد از Active شدن استفاده می‌شوند.

---

## مرحله 6 — تست‌ها به این ترتیب

### تست 1
در Telegram:

`آکورد E رو یادم بده`

باید پاسخ متنی بگیری.

### تست 2

`عکس آکورد E رو بده`

باید ابتدا پیام شروع پردازش و بعد PNG دریافت کنی.

### تست 3
یک MP3 زیر 20MB بفرست.

خروجی مورد انتظار:

- متن تحلیل
- MP3 تمرینی
- GP5

### تست 4
بعد از همان MP3 بنویس:

`آهسته‌تر بزن و با مترونوم بفرست`

سیستم باید از Session همان کاربر استفاده کند و arrangement جدید بسازد.

### تست 5
یک ویدیوی گیتار زیر 20MB بفرست.

خروجی مورد انتظار:

- متن خلاصه
- GP5
- MIDI

---

## اگر چیزی Fail شد

اول در GitHub Repository به تب **Actions** برو و Workflow `Guitar AI Processor` را باز کن.

اگر Job اصلاً شروع نشده، مشکل معمولاً GitHub PAT / Project Config است.

اگر Job شروع شده ولی `Read job type` Fail شده، `N8N_JOB_URL` یا `N8N_CALLBACK_SECRET` را چک کن.

اگر Telegram download خطا داد، حجم فایل و `TELEGRAM_BOT_TOKEN` را چک کن.

اگر Video job در Basic Pitch خطا داد، لاگ همان Step مشخص می‌کند مشکل dependency یا audio بوده است.
