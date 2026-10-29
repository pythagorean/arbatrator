PREFIX ?= $(HOME)/.local
BINDIR = $(PREFIX)/bin
DATADIR = $(PREFIX)/share/arbatrate

SHELL_SCRIPTS = host/arbatrate-host \
	appliance/rootfs/usr/local/bin/arbatrate-entrypoint \
	appliance/rootfs/usr/local/bin/arbatrate-audio-out

.PHONY: install uninstall check test lint

install:
	install -d $(BINDIR) $(DATADIR)
	install -m 0755 client/arbatrate $(BINDIR)/arbatrate
	rm -rf $(DATADIR)/appliance $(DATADIR)/host
	cp -R appliance host $(DATADIR)/

uninstall:
	rm -f $(BINDIR)/arbatrate
	rm -rf $(DATADIR)

check: test lint

test:
	python3 -m unittest discover -s tests

lint:
	shellcheck $(SHELL_SCRIPTS)
	node --check appliance/extension/background.js
	node --check appliance/extension/content.js
	python3 -m json.tool appliance/extension/manifest.json >/dev/null
	python3 -m json.tool appliance/seccomp-chromium.json >/dev/null
