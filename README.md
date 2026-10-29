# Arbatrate

**A remote browser appliance to receive all types of resources.**

Arbatrate runs Chromium inside a Podman container on another machine (usually
a VM) and shows it on your own Wayland desktop through
[waypipe](https://gitlab.freedesktop.org/mstoeckl/waypipe). The browser has
its own persistent profile, its own network location and its own audio
graph. Its sound is captured from PipeWire and streamed to you as Opus. Media
on a page can be handed off to a player on your machine, either relayed
through the appliance or fetched by your player directly.

Protected (DRM) media is never handed off. It plays in the remote browser
only.

```
 your machine (client)                         appliance host (VM)
┌──────────────────────────┐                  ┌──────────────────────────────────────┐
│ arbatrate                │  one SSH         │ arbatrate-host                       │
│  ├ waypipe client ◄──────┼── connection ────┼─► waypipe server                     │
│  │  (window on your      │  (multiplexed)   │     └ podman run arbatrate-PROFILE   │
│  │   desktop)            │                  │        ├ Chromium (Wayland)          │
│  ├ audio player ◄────────┼── Ogg/Opus ──────┼────────┤  └ extension → native host  │
│  │  (mpv)                │                  │        ├ PipeWire → "arbatrate" sink │
│  └ handoff player ◄──────┼── media ─────────┼────────┤   └ arbatrate-audio-out      │
│     (mpv)                │                  │        └ arbatrate-handoff-stream    │
└──────────────────────────┘                  │           arbatrate-fetch (yt-dlp)   │
                                              └──────────────────────────────────────┘
```

## What you need

**On your machine:** a Wayland session, `waypipe`, `ssh`, Python 3.11 or
newer, and `mpv` (or another player you configure).

**On the appliance host:** `podman` 4.3 or newer (rootless), `waypipe` (the
same version as on your machine), and an `XDG_RUNTIME_DIR` for the SSH user.
On a systemd host, `loginctl enable-linger USER` gives the user one without
a desktop login.

## Setup

On your machine, from a checkout of this repository:

```bash
make install
```

This installs `arbatrate` into `~/.local/bin` and the appliance sources into
`~/.local/share/arbatrate`. `make install PREFIX=/usr/local` installs
elsewhere.

Write `~/.config/arbatrate/config.toml`. Only `host` is required; the
example lists every setting with its default:

```bash
mkdir -p ~/.config/arbatrate
```

```bash
cp client/config.example.toml ~/.config/arbatrate/config.toml
```

Copy the appliance to the host and build its image there:

```bash
arbatrate install-host
```

Check both ends:

```bash
arbatrate doctor
```

## Use

```bash
arbatrate
```

opens the browser for the default profile. `arbatrate --profile work` opens
another one; each profile is its own podman volume (`arbatrate-profile-NAME`)
and its own container, so several can run at once.

Close the browser window, or press Ctrl-C in the terminal, to end the
session. The container is removed; the profile volume stays.

### Handing media off

In the remote browser:

- right-click a video or audio element: **Play locally**
- right-click a link: **Play link locally**
- right-click the page, or click the Arbatrate toolbar button:
  **Play this page's media locally**

The playback position comes along, and the remote element is paused.

There are two modes (`[handoff] mode` in the configuration):

- **relay** (default): the appliance resolves the media with yt-dlp, using
  the browser profile's cookies, fetches it with ffmpeg and streams it over
  SSH to your player. The site only ever sees the appliance. Set
  `relay_transcode` to re-encode for a weak client.
- **local**: your player is given the URL and fetches it itself.

You can also hand off a URL from the terminal: `arbatrate play URL`.

### Protected media

The extension treats a media element as protected once it has DRM keys
attached (`MediaKeys`) or has raised an `encrypted` event, and refuses to
hand it off. yt-dlp, which resolves every relayed URL, refuses DRM-protected
formats as well, and Arbatrate does not ask it to do otherwise.

## Design notes

- **Nothing is restarted.** The session is a set of processes that live and
  die together. If any one of them ends (Chromium, PipeWire, the audio
  stream, the waypipe connection), the whole session ends and says which
  one it was. A fault you can see is a fault you can fix.
- **One SSH connection.** Everything is multiplexed over an SSH control
  master, so the host needs nothing listening but `sshd`.
- **Settings are configuration, not code.** Everything a deployment would
  want to change is in the client's configuration file and travels to the
  host as `ARBATRATE_*` environment variables.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit
together and why.

## Development

```bash
make check
```

runs the unit tests, `shellcheck` and a syntax check of the extension.

The image's base can be overridden for mirrors:
`podman build --build-arg BASE=… appliance`.

## License

MIT. See [LICENSE](LICENSE). `appliance/seccomp-chromium.json` is derived
from the Moby project's default seccomp profile (Apache-2.0); see
[NOTICE](NOTICE).
