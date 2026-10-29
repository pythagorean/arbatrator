// Arbatrate content script: finds media elements for the background worker
// and reports whether each one is protected.
//
// An element counts as protected once it has MediaKeys attached or has fired
// an "encrypted" event. Protected media is never offered for handoff; it
// plays in the browser only.
"use strict";

const encrypted = new WeakSet();
document.addEventListener("encrypted", (e) => encrypted.add(e.target), true);

function isProtected(el) {
  return encrypted.has(el) || el.mediaKeys != null;
}

function mediaElements() {
  return Array.from(document.querySelectorAll("video, audio"));
}

// The element the user most plausibly means: one that is playing, else the
// largest visible video, else the first media element.
function mainElement() {
  const all = mediaElements();
  const playing = all.find((el) => !el.paused && !el.ended);
  if (playing) return playing;
  let best = null;
  let bestArea = 0;
  for (const el of all) {
    const r = el.getBoundingClientRect();
    const area = r.width * r.height;
    if (area > bestArea) {
      best = el;
      bestArea = area;
    }
  }
  return best || all[0] || null;
}

function findElement(srcUrl) {
  if (!srcUrl) return mainElement();
  return mediaElements().find((el) => el.currentSrc === srcUrl || el.src === srcUrl) || null;
}

function describe(el) {
  const base = { page_url: location.href, title: document.title };
  if (!el) return { ...base, found: false };
  return {
    ...base,
    found: true,
    protected: isProtected(el),
    src: el.currentSrc || el.src || "",
    start: Number.isFinite(el.currentTime) ? el.currentTime : null,
  };
}

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.cmd === "probe") {
    reply(describe(findElement(msg.srcUrl)));
  } else if (msg.cmd === "pause") {
    const el = findElement(msg.srcUrl);
    if (el) el.pause();
    reply({});
  }
});
