# Architecture

Arbatrate has three parts:

| Part | Runs on | What it is |
|---|---|---|
| `client/arbatrate` | your machine | Python CLI: brings the session up, plays audio, acts on handoffs |
| `host/arbatrate-host` | appliance host | Bash: builds the image, runs and stops containers |
| `appliance/` | inside the container | Chromium, PipeWire, the extension and its helpers |

## A session, step by step

1. **SSH control master.** The client opens one SSH connection with
   `ControlMaster`. Every later SSH call, including waypipe's, rides on it.
2. **Display.** The client runs
   `waypipe ssh HOST arbatrate-host run PROFILE`. waypipe's server on the
   host creates a Wayland socket and runs `arbatrate-host`, which starts the
   container with that socket bind-mounted in. Chromium runs with
   `--ozone-platform=wayland` and draws to it; waypipe carries the
   protocol and buffers to your desktop.
3. **Ready.** The container's entrypoint starts a session D-Bus, PipeWire,
   WirePlumber and pipewire-pulse, each after the socket of the one before
   it exists, then Chromium, then writes a `ready` file. The client waits
   for that file with `arbatrate-host wait-ready`, and stops waiting at once
   if the browser side has already failed.
4. **Audio.** PipeWire has one sink, `arbatrate`, a null sink that is the
   default output. `arbatrate-audio-out` records its monitor with ffmpeg and
   writes Ogg/Opus to stdout, one Ogg page per 10 ms Opus frame so nothing
   waits in the muxer. The client pipes it into a local player.
5. **Handoff channel.** The client runs `arbatrate-handoff-stream`, which
   listens on a Unix socket inside the container and writes each request it
   accepts to stdout as one JSON line.
6. **Teardown.** When any of these processes ends, the client stops the
   others, runs `arbatrate-host stop`, closes the control master and exits
   with the status of the process that ended.

## Handoff

```
page ─► content.js ─► background.js ─► arbatrate-native-host ─► handoff.sock
                                                                    │
client ◄── JSON line ◄── arbatrate-handoff-stream ◄─────────────────┘
   │
   ├─ relay: ssh … arbatrate-fetch REQUEST | relay_player
   └─ local: local_player URL
```

- **content.js** runs in every frame. It records which media elements have
  raised `encrypted` and answers probes from the background worker with the
  element's source, the page URL, the title, the playback position and
  whether the element is protected.
- **background.js** adds the context menu items and the toolbar action. It
  refuses protected elements. Otherwise it builds a request: the element's
  own source when that is an http(s) URL, else the page URL (a `blob:` or
  MediaSource source can only be found again through its page).
- **arbatrate-native-host** is a Chromium native-messaging host. The
  extension has a fixed ID (from the `key` in its manifest) and the host's
  manifest allows only that ID. It forwards the request to the stream's
  socket and returns the reply, so the extension can tell the user when no
  client is attached.
- **arbatrate-fetch** (relay mode) resolves the URL with yt-dlp, using the
  profile's cookies, and runs ffmpeg on the resulting media URLs with the
  headers yt-dlp gives. The output is Matroska on stdout: streams copied, or
  re-encoded if `relay_transcode` is set.

Requests are checked at each hop: only `http`/`https` URLs and plain values
pass. The client does not trust the appliance to choose what runs locally;
the request only fills placeholders in a player command you configured, and
it is never passed through a shell.

## Containment

- The container runs rootless with `--userns=keep-id:uid=1000,gid=1000`, so
  the browser user inside is your user on the host and can use the
  forwarded Wayland socket.
- Chromium's own sandbox stays on. It needs to create user, PID and network
  namespaces, which the default container seccomp profile forbids;
  `appliance/seccomp-chromium.json` is the default profile plus exactly
  that.
- The profile lives in a named volume per profile mounted at
  `/home/browser`. Everything else is discarded when the container exits.

## Known limits

- **A/V sync in the remote browser.** Picture and sound travel separate
  paths (waypipe and the audio stream), so video watched *in* the remote
  browser can drift slightly out of lip sync. For watching video, hand it
  off; that is what handoff is for.
- **Relay formats.** The default format selector prefers formats ffmpeg can
  read straight from a URL. DASH fragment lists are skipped, which on some
  sites means a lower quality than the browser shows. `relay_format` takes
  any yt-dlp selector.
- **GPU.** Nothing is configured for GPU use. On a VM without one, Chromium
  renders in software and waypipe sends shared-memory buffers; this works,
  and `--compress` settles the bandwidth.
