# Contributing

Bug reports and pull requests are welcome.

## Getting set up

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/pr0digy91/agent-rooms
cd agent-rooms
uv sync --all-groups
cp .env.example .env        # then add your XAI_API_KEY
uv run streamlit run app.py
```

`uv.lock` is committed and should be kept in step with `pyproject.toml`: run
`uv lock` after changing dependencies and include the result in your PR.

## Layout

Each module does one thing. If a change blurs two of these together, say why in
the PR.

| module | role |
|---|---|
| `app.py` | the Streamlit UI; holds no simulation logic |
| `sim.py` | storage, memory, speaker selection, manifestations, turn generation |
| `voice.py` | xAI speech calls, and the validator for marked-up delivery |
| `player.py` | browser JavaScript for queued audio and device selection |
| `style.py` | the dark and light themes |

## Tests

```sh
uv run pytest -q
uv run ruff check .
```

The tests need **no API key and no network**, and CI runs them without one. Model
calls are scripted with `ag2.testing.TestConfig`, or captured by replacing
`sim._ask_sync`. Keep it that way: a test that reaches a real model costs money
and fails for reasons unrelated to the code.

`tests/conftest.py` points storage at a temporary directory for every test, so
nothing can touch a real `agent_rooms.db`. If you add a new data file, redirect
it there too.

The tests cannot see the browser. Changes to `player.py` or `style.py` need
checking by hand, in both themes, and audio changes in Chrome as well as one
other browser.

## Things that will bite you

- **Streamlit silently drops a whole script if its text looks like markup**, even
  inside a comment. `_html_with_script` in `player.py` raises when it sees this,
  so avoid writing tags in the JavaScript, including in comments.
- **Streamlit's styled elements change between versions.** It uses React Aria, so
  CSS in `style.py` targets `data-testid` attributes. Check both themes after
  upgrading, especially dropdowns and open expanders.
- **Persistent widgets take their value from session state.** A setting in `PREFS`
  in `app.py` must have its widget use `key=` and no `value=`.
- **Schema changes need a migration.** People have data in `agent_rooms.db`. Add
  new columns in `sim._db()`, and add a test to `tests/test_storage.py` that opens
  the old shape.
- **Keep one asyncio loop.** `run_async` exists because running a new loop per turn
  breaks the pooled HTTP client with `Event loop is closed`.

## Style

Match what is already there.

- **Mind the bill.** Everyone running this pays per call. If a change adds model or
  voice calls per turn, make it optional and say so in the PR.
- **Comments explain why, not what.**
- **Keep it easy to run.** New dependencies should earn their place in the PR
  description.

## Versioning

There is one version number, in `pyproject.toml`. The page reads it from there.

- **Patch** (0.1.1): fixes, with nothing a user has to do.
- **Minor** (0.2.0): new features, or anything that needs action on upgrade.
- **1.0.0** is a promise that every later version opens an existing
  `agent_rooms.db`. Until then the schema is still moving, though a release should
  still migrate old data rather than drop it.

## Releasing

1. Bump the version in `pyproject.toml`, then run `uv lock`.
2. Commit only that, as `Version 0.2.0`. The body says why this is a patch or a
   minor, and what changed.
3. Wait for CI to pass on that commit, then tag it. The tag message is one line:

   ```sh
   git tag -a v0.2.0 -m "Saved conversations can be renamed"
   git push origin v0.2.0
   ```

4. Publish a GitHub release from the tag, named after it:

   ```sh
   gh release create v0.2.0 --verify-tag --title v0.2.0 --notes-file notes.md
   ```

Tagging can be undone right up to step 4. Publishing is the moment users see it.

The notes open with **what happens to existing data**, because that is the first
thing anyone upgrading needs to know, for example "Your saved characters and
conversations are unaffected." Then give each change a heading that states what
now happens, and a short paragraph on what was wrong before. Call out anything
that adds model or voice calls.

Publishing runs `.github/workflows/release.yml`, which checks that the tag matches
the version and runs the tests and lint on the tagged commit.

## Pull requests

Keep each PR to one change. Describe what you tested by hand, since the suite
covers logic and not sound or layout. Screenshots help for anything visual.
