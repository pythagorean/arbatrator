// Arbatrate background worker: turns the user's choice into a handoff
// request and passes it to the native host, which hands it to the client.
"use strict";

const HOST = "org.arbatrate.handoff";

function isHttp(url) {
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

function notify(message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icon128.png",
    title: "Arbatrate",
    message,
  });
}

async function probe(tabId, frameId, srcUrl) {
  try {
    return await chrome.tabs.sendMessage(tabId, { cmd: "probe", srcUrl }, { frameId });
  } catch {
    return null; // no content script in that frame (e.g. a browser page)
  }
}

// Build the request from a probe. The element's own source is used when it
// is a plain URL; blob: and MediaSource sources can only be found again
// through the page they belong to.
function requestFrom(found, fallback) {
  const url = found && isHttp(found.src) ? found.src : (found && found.page_url) || fallback.page_url;
  return {
    type: "play",
    url,
    page_url: (found && found.page_url) || fallback.page_url,
    title: (found && found.title) || fallback.title || "",
    start: found && found.start != null ? found.start : null,
  };
}

async function handoff(tab, frameId, srcUrl, fallback) {
  const found = await probe(tab.id, frameId, srcUrl);
  if (found && found.found && found.protected) {
    notify("This media is protected (DRM). It can only play here, in the browser.");
    return;
  }
  const request = requestFrom(found && found.found ? found : null, fallback);
  if (!isHttp(request.url)) {
    notify("Nothing here can be handed off.");
    return;
  }
  let reply;
  try {
    reply = await chrome.runtime.sendNativeMessage(HOST, request);
  } catch (e) {
    notify(`The handoff helper is not available: ${e.message}`);
    return;
  }
  if (!reply.ok) {
    notify(reply.error);
    return;
  }
  if (found && found.found) {
    chrome.tabs.sendMessage(tab.id, { cmd: "pause", srcUrl }, { frameId }).catch(() => {});
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "media", title: "Play locally", contexts: ["video", "audio"] });
  chrome.contextMenus.create({ id: "link", title: "Play link locally", contexts: ["link"] });
  chrome.contextMenus.create({ id: "page", title: "Play this page's media locally", contexts: ["page"] });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  const fallback = { page_url: info.frameUrl || info.pageUrl, title: tab.title };
  if (info.menuItemId === "media") {
    handoff(tab, info.frameId, info.srcUrl, fallback);
  } else if (info.menuItemId === "link") {
    // A link has no element to probe; yt-dlp still refuses protected media.
    handoff(tab, -1, null, { page_url: info.linkUrl, title: "" });
  } else if (info.menuItemId === "page") {
    handoff(tab, 0, null, { page_url: info.pageUrl, title: tab.title });
  }
});

chrome.action.onClicked.addListener((tab) => {
  handoff(tab, 0, null, { page_url: tab.url, title: tab.title });
});
