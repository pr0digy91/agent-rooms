# Security

## Reporting a vulnerability

Please do not open a public issue. Use
[private vulnerability reporting](https://github.com/pr0digy91/agent-rooms/security/advisories/new)
with the steps to reproduce and what an attacker could do with it.

This is a project maintained in spare time, so replies may take a few days.

## Your API key

The app reads `XAI_API_KEY` from a local `.env` file, which is git-ignored. The
key is sent only to `api.x.ai`, and is never stored in the database.

- Never commit `.env`, and never paste the key into an issue or a log.
- If a key may have leaked, rotate it in the [xAI console](https://console.x.ai).
  Removing it from a later commit does not remove it from history.

## Running it safely

Agent Rooms is a single-user local app. **It has no login.** Anyone who can open
the page can read your conversations and spend your API credit.

Streamlit listens on all network interfaces by default, so the app is reachable
from your local network. To keep it on your own machine:

```bash
uv run streamlit run app.py --server.address localhost
```

Do not put it on the public internet without authentication in front of it.

## Your data

Characters, rooms, settings, conversations and audio clips are stored unencrypted
in `agent_rooms.db`, next to the code. The file is git-ignored. Conversation text
is sent to xAI to generate replies, and spoken lines and mic audio are sent to
xAI for speech. See xAI's terms for how that data is handled.
