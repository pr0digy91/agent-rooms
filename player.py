"""Browser-side audio: one shared <audio> element unlocked by the user's first click/keypress,
with a queue so lines play in order and a hint if the browser still blocks autoplay."""

from __future__ import annotations

import base64
import re

import streamlit as st


PLAYER_JS = """
(function () {
  const w = window;
  if (!w.__ar) {
    const ar = w.__ar = {a: new Audio(), q: [], busy: false, unlocked: false};
    const saved = (k) => { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } };
    // Output device (headphones): route every audio element on the page, including the per-message players.
    ar.applySink = (el) => { if (el && el.setSinkId) el.setSinkId(saved("ar.spk")).catch(() => {}); };
    ar.applySink(ar.a);
    document.querySelectorAll("audio").forEach(ar.applySink);
    new MutationObserver((muts) => muts.forEach((m) => m.addedNodes.forEach((n) => {
      if (n.nodeType !== 1) return;
      (n.tagName === "AUDIO" ? [n] : n.querySelectorAll("audio")).forEach(ar.applySink);
    }))).observe(document.body, {childList: true, subtree: true});
    // Input device (mic): Streamlit's mic button always asks for the default device, so add the
    // chosen one to its request. If that device was unplugged, fall back to the default.
    const md = navigator.mediaDevices;
    if (md && md.getUserMedia && !md.__arWrapped) {
      const orig = md.getUserMedia.bind(md);
      md.getUserMedia = (c) => {
        const id = saved("ar.mic");
        if (!id || !c || !c.audio) return orig(c);
        const withId = Object.assign({}, c, {audio: Object.assign({}, c.audio === true ? {} : c.audio, {deviceId: {exact: id}})});
        return orig(withId).catch((err) => {
          if (err && (err.name === "OverconstrainedError" || err.name === "NotFoundError")) return orig(c);
          throw err;
        });
      };
      md.__arWrapped = true;
    }
    const SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
    const hint = (on) => {
      let el = document.getElementById("ar-hint");
      if (on && !el) {
        el = document.createElement("div"); el.id = "ar-hint";
        el.textContent = "🔇 Your browser blocked autoplay. Click anywhere on the page to enable voice.";
        el.style.cssText = "position:fixed;bottom:16px;right:16px;z-index:99999;background:#b45309;" +
          "color:#fff;padding:10px 14px;border-radius:12px;font:14px sans-serif;box-shadow:0 8px 24px #0006;";
        document.body.appendChild(el);
      } else if (!on && el) { el.remove(); }
    };
    ar.next = () => {
      if (ar.busy || !ar.q.length) return;
      const src = ar.q.shift(); ar.busy = true; ar.a.src = src;
      ar.a.play().then(() => { ar.unlocked = true; hint(false); })
        .catch(() => { ar.q.unshift(src); ar.busy = false; hint(true); });
    };
    ar.a.addEventListener("ended", () => { ar.busy = false; ar.next(); });
    ar.a.addEventListener("error", () => { ar.busy = false; ar.next(); });
    const unlock = () => {
      if (ar.unlocked) return;
      if (ar.q.length && !ar.busy) { ar.next(); return; }
      if (ar.busy) return;
      ar.busy = true; ar.a.src = SILENT;
      ar.a.play().then(() => { ar.unlocked = true; hint(false); }).catch(() => { ar.busy = false; });
    };
    ["pointerdown", "keydown", "touchstart"].forEach((e) => document.addEventListener(e, unlock, true));
  }
  const clip = __CLIP__;
  if (clip) { w.__ar.q.push("data:audio/mpeg;base64," + clip); w.__ar.next(); }
})();
"""


def _html_with_script(js: str, before: str = "") -> None:
    """Render a script via st.html. Streamlit's sanitiser silently drops a whole script if its text
    looks like markup (e.g. a comment or string containing '<audio>'), so fail loudly instead."""
    if re.search(r"<[A-Za-z/!?]", js):
        raise ValueError("Script text must not contain '<' followed by a letter or '/': " + re.search(r".{0,30}<[A-Za-z/!?].{0,30}", js).group(0))
    # a script-only snippet can also be dropped, so it always travels with an element
    st.html(f"{before or '<span hidden></span>'}<script>{js}</script>", unsafe_allow_javascript=True)


def run_player(mp3: bytes | None = None) -> None:
    """Install the shared player (idempotent) and optionally queue an mp3 to play now."""
    clip = base64.b64encode(mp3).decode() if mp3 else ""
    _html_with_script(PLAYER_JS.replace("__CLIP__", repr(clip)))


DEVICES_JS = """
(function () {
  const root = document.getElementById("ar-dev");
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const get = (k) => { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } };
  const set = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  const el = (tag, props, text) => { const e = Object.assign(document.createElement(tag), props || {}); if (text) e.textContent = text; return e; };
  const field = (label) => { const w = el("div", {className: "ar-field"}); w.append(el("label", {}, label)); return w; };

  const micSel = el("select"), spkSel = el("select");
  const note = el("div", {className: "ar-note"});
  const allow = el("button", {type: "button", className: "ar-btn"}, "Allow microphone access to show device names");
  const test = el("button", {type: "button", className: "ar-btn"}, "Play test sound");
  const micF = field("Microphone"), spkF = field("Headphones / speakers");
  micF.append(micSel); spkF.append(spkSel);
  root.append(micF, spkF, test, allow, note);

  const beep = () => {  // 0.5s 440 Hz tone as a WAV, played on the chosen output
    const rate = 22050, n = rate / 2, buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
    const s = (o, t) => [...t].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
    s(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); s(8, "WAVEfmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
    v.setUint16(22, 1, true); v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true);
    v.setUint16(34, 16, true); s(36, "data"); v.setUint32(40, n * 2, true);
    for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.sin(2 * Math.PI * 440 * i / rate) * 9000 * Math.min(1, (n - i) / 2000), true);
    return URL.createObjectURL(new Blob([buf], {type: "audio/wav"}));
  };

  const fill = (sel, devices, saved, fallback) => {
    sel.replaceChildren(el("option", {value: ""}, "System default"));
    devices.filter((d) => d.deviceId !== "default" && d.deviceId !== "communications").forEach((d, i) =>
      sel.append(el("option", {value: d.deviceId}, d.label || fallback + " " + (i + 1))));
    sel.value = [...sel.options].some((o) => o.value === saved) ? saved : "";
  };
  const refresh = async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) { note.textContent = "This browser can't list audio devices."; return; }
    const devs = await navigator.mediaDevices.enumerateDevices();
    const ins = devs.filter((d) => d.kind === "audioinput"), outs = devs.filter((d) => d.kind === "audiooutput");
    fill(micSel, ins, get("ar.mic"), "Microphone");
    fill(spkSel, outs, get("ar.spk"), "Output");
    allow.style.display = ins.some((d) => d.label) ? "none" : "";
    const canSink = "setSinkId" in HTMLMediaElement.prototype;
    spkSel.disabled = !canSink;
    note.textContent = canSink ? "" : "Choosing the output device isn't supported in this browser (try Chrome or Edge). Audio uses your system default.";
  };
  micSel.onchange = () => set("ar.mic", micSel.value);
  spkSel.onchange = () => {
    set("ar.spk", spkSel.value);
    const ar = window.__ar;
    if (ar) { ar.applySink(ar.a); document.querySelectorAll("audio").forEach(ar.applySink); }
  };
  test.onclick = () => {
    const a = new Audio(beep());
    if (a.setSinkId) a.setSinkId(get("ar.spk")).catch(() => {}).finally(() => a.play()); else a.play();
  };
  allow.onclick = async () => {
    try { (await navigator.mediaDevices.getUserMedia({audio: true})).getTracks().forEach((t) => t.stop()); }
    catch (e) { note.textContent = "Microphone permission was denied."; }
    refresh();
  };
  if (navigator.mediaDevices) navigator.mediaDevices.addEventListener("devicechange", refresh);
  refresh();
})();
"""


def device_picker() -> None:
    """Dropdowns for the browser's microphone and output device, saved in the browser's localStorage."""
    _html_with_script(DEVICES_JS, '<div id="ar-dev"></div>')
