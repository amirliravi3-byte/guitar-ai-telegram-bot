from __future__ import annotations
import os, time, requests

HEADER = "X-Guitar-AI-Secret"


def _secret_headers():
    secret = os.getenv("N8N_CALLBACK_SECRET", "").strip()
    if not secret:
        raise RuntimeError("N8N_CALLBACK_SECRET is not configured")
    return {HEADER: secret, "Content-Type": "application/json"}


def fetch_job(job_id: str, attempts: int = 12, delay_seconds: int = 5) -> dict:
    """Fetch an opaque job payload from n8n.

    A short retry loop handles the small persistence race that can occur because
    n8n workflow static data is committed when the dispatch execution finishes.
    """
    url = os.getenv("N8N_JOB_URL", "").strip()
    if not url:
        raise RuntimeError("N8N_JOB_URL is not configured")
    last_error = None
    for attempt in range(max(1, attempts)):
        try:
            r = requests.post(url, json={"job_id": str(job_id)}, headers=_secret_headers(), timeout=30)
            r.raise_for_status()
            data = r.json()
            if data.get("ok") and isinstance(data.get("job"), dict):
                return data["job"]
            last_error = RuntimeError(data.get("error") or "job not ready")
        except Exception as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(delay_seconds)
    raise RuntimeError(f"Could not retrieve job {job_id}: {last_error}")


def post_state(chat_id, state, job_id="", user_id=""):
    url = os.getenv("N8N_CALLBACK_URL", "").strip()
    if not url:
        return False
    payload = {"chat_id": str(chat_id), "user_id": str(user_id or ""), "state": state, "job_id": str(job_id or "")}
    r = requests.post(url, json=payload, headers=_secret_headers(), timeout=30)
    r.raise_for_status()
    return True
