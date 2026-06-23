# German Tutor Bot — Webhook Listener Setup

This is the "always-on" piece of your system: it receives every WhatsApp message you send
(text or voice), runs it through Claude, and replies — plus an endpoint that GitHub Actions
pings twice a day for your scheduled lessons.

## What's in this folder

| File | Purpose |
|---|---|
| `app.py` | Flask app — the webhook itself |
| `config.py` | Reads all secrets/settings from environment variables |
| `storage.py` | Progress tracking (JSON file for now, swap for Supabase later) |
| `roadmap.py` | Your A1 tier content, structured for the system prompt |
| `tutor_brain.py` | Builds the system prompt, calls Claude, parses structured response |
| `whatsapp_client.py` | Sends/receives messages via Meta's WhatsApp Cloud API |
| `speech.py` | Azure Speech: text-to-speech and speech-to-text |
| `.github/workflows/scheduled_lessons.yml` | Cron job that triggers morning/evening lessons |
| `requirements.txt` | Python dependencies |

## Before you run anything

You'll need accounts/keys for:
1. **Anthropic** — your Claude API key
2. **Meta for Developers** — a WhatsApp Business app (we'll set this up next, in the WhatsApp API step)
3. **Azure** — a free-tier Speech resource (for TTS/STT)
4. **A free hosting platform** that can run a persistent web service — Render.com's free tier is the easiest fit for Flask. (PythonAnywhere also works.)

## Environment variables you'll need to set on your host

```
META_ACCESS_TOKEN=...
META_PHONE_NUMBER_ID=...
META_VERIFY_TOKEN=choose-any-string-yourself
ANTHROPIC_API_KEY=...
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=westeurope        # or whatever region you chose
YOUR_WHATSAPP_NUMBER=2376XXXXXXXXX   # your number, digits only, country code, no +
WEBHOOK_SHARED_SECRET=choose-any-string-yourself
```

`META_VERIFY_TOKEN` and `WEBHOOK_SHARED_SECRET` are NOT given to you by anyone — you invent
these strings yourself and use the same value in both Meta's webhook setup / your GitHub
Actions secrets and here.

## Local testing (before deploying anywhere)

```bash
cd german_tutor_bot
python -m venv venv
source venv/bin/activate          # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**One extra system dependency:** `pydub` needs `ffmpeg` installed on whatever machine runs this.
- Mac: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: download from ffmpeg.org and add to PATH
- On Render.com: add a `render-build.sh` that runs `apt-get install -y ffmpeg` (I can help with this when we deploy)

Then run it locally:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
# ... set the other env vars too, or use a .env file with python-dotenv
python app.py
```

This starts the Flask server on `localhost:5000`. You can't test inbound WhatsApp messages
locally without exposing this to the internet (Meta needs to reach your webhook) — for that,
use a tool like `ngrok` during testing:
```bash
ngrok http 5000
```
This gives you a temporary public URL to use as your webhook URL in Meta's settings while testing.

## Testing the scheduled-lesson endpoint manually (no GitHub Actions needed yet)

```bash
curl -X POST http://localhost:5000/send-lesson \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-chosen-secret" \
  -d '{"session_type": "morning"}'
```

If everything's wired correctly, you should get a WhatsApp message on your phone.

## Deploying for real (so it runs 24/7 for free)

1. Push this folder to a GitHub repo (private is fine)
2. Create a free Render.com Web Service, point it at your repo
3. Set the environment variables above in Render's dashboard
4. Add the ffmpeg build step (ask me when you get here — depends on Render's exact build config)
5. Render gives you a permanent URL like `https://your-app.onrender.com` — this becomes your webhook base URL
6. In GitHub repo Settings → Secrets, add `WEBHOOK_BASE_URL` (your Render URL) and `WEBHOOK_SHARED_SECRET` (same value as on Render) so the Actions cron can call it

**One caveat about Render's free tier:** free web services "sleep" after 15 minutes of no traffic
and take a few seconds to wake up on the next request. For a scheduled lesson trigger this is fine
(GitHub Actions will just wait a moment for the response) — for an inbound WhatsApp reply, it means
your first message after a quiet period might get a delayed response. Not a deal-breaker for personal use.

## Next steps after this

We still need to:
1. Register the Meta WhatsApp Cloud API app and get your real `META_ACCESS_TOKEN` / `META_PHONE_NUMBER_ID`
2. Point Meta's webhook settings at your deployed URL
3. Set up the Azure Speech resource and grab those keys
4. Do a live end-to-end test
