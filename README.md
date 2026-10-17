# Agent Rooms

A Streamlit app where AI characters live in customizable rooms and talk to each other, and to you. Built on [AG2](https://github.com/ag2ai/ag2) and xAI Grok, with voice in and out.

## Features

- **Characters**: give each one a persona, a behaviour and a voice.
- **Rooms**: define the environment and its rules. Run any cast in any room.
- **You in the scene**: join under your own name and persona, by typing or by voice.
- **Who speaks next**: Director (Grok picks the most natural reply), Round robin or Random. Whoever you address by name replies next.
- **Memory**: a rolling summary of older turns, plus private notes per character.
- **Manifestation box**: introduce an idea, artifact, physical object, entity or phenomenon and every character becomes aware of it at once. Each item has a **conviction** (0-100): how firmly everyone believes in it and what it claims. At 85 or higher it is accepted as plain truth; at 15 or lower it is resisted.
- **Voice**: mic input, spoken replies that autoplay in each character's voice, and tempo and rhythm shaped by the scene and the character's history (Subtle, Natural or Dramatic delivery).
- **Audio devices**: pick your microphone and headphones (headphone routing needs Chrome or Edge).
- **Save and load**: conversations are stored with their memory, manifestations and audio clips.
- **Dark and light themes**.
- **Everything persists** in SQLite: characters, rooms, your player, settings and conversations.

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Create a `.env` file in the project root:

```env
XAI_API_KEY=your-key-here

# optional
XAI_MODEL=grok-4.20-0309-non-reasoning
XAI_STT_MODEL=grok-voice-transcribe-2.0
XAI_TTS_LANGUAGE=en
XAI_DEFAULT_VOICE=eve
```

Get a key from the [xAI console](https://console.x.ai). `.env` is git-ignored; never commit it.

## Run

```bash
uv run streamlit run app.py
```

Restart the server after pulling changes.

## Using it

1. **Characters** and **Rooms** tabs: create or edit your cast and settings.
2. **Simulation** tab: pick a room and who is present, then press **Next** or **Run 5 turns**, or type or speak to the room.
3. Tick **Auto-respond when I speak** to get replies without pressing Next.
4. Turn on **Speak replies aloud** under **Options** for voiced replies.
5. Use the **Manifestation box** to change the shared reality and watch the room react.

Note: every turn is a model call, and memory, delivery planning, speech and reactions to a manifestation each add calls.

## Data and files

| Path | What it is |
|---|---|
| `agent_rooms.db` | SQLite database holding all your data. Git-ignored; back it up if you care about it. |
| `state.json` | Legacy file, imported once into the database. |
| `app.py` | Streamlit UI |
| `sim.py` | Storage, memory, speaker selection, manifestations and turn generation |
| `voice.py` | xAI text-to-speech and speech-to-text |
| `player.py` | Browser audio player and device picker |
| `style.py` | Theme and CSS |

## Tech

AG2 1.1.2 for the agents, xAI Grok (OpenAI-compatible API) for text, the xAI `/v1/tts` and `/v1/stt` endpoints for voice, Streamlit for the UI and SQLite for storage.
