import importlib.machinery
import importlib.util
import shlex
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


client = load("arbatrate_client", ROOT / "client" / "arbatrate")
handoff = load("arbatrate_handoff", ROOT / "appliance/rootfs/usr/local/lib/arbatrate/handoff.py")


class ConfigTest(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(Path(f.name).unlink)
        return Path(f.name)

    def test_defaults_when_file_missing(self):
        cfg = client.load_config(Path("/nonexistent/config.toml"))
        self.assertEqual(cfg["profile"], "default")
        self.assertEqual(cfg["handoff"]["mode"], "relay")

    def test_override_merges_tables(self):
        cfg = client.load_config(self.write('host = "me@vm"\n[audio]\nbitrate = "96k"\n'))
        self.assertEqual(cfg["host"], "me@vm")
        self.assertEqual(cfg["audio"]["bitrate"], "96k")
        self.assertTrue(cfg["audio"]["enabled"])

    def test_unknown_setting_is_an_error(self):
        with self.assertRaisesRegex(client.ConfigError, "audio.bitrat"):
            client.load_config(self.write('[audio]\nbitrat = "96k"\n'))

    def test_wrong_type_is_an_error(self):
        with self.assertRaises(client.ConfigError):
            client.load_config(self.write("[audio]\nframe_ms = \"10\"\n"))

    def test_bad_mode_is_an_error(self):
        with self.assertRaises(client.ConfigError):
            client.load_config(self.write('[handoff]\nmode = "teleport"\n'))

    def test_example_config_loads(self):
        cfg = client.load_config(ROOT / "client" / "config.example.toml")
        self.assertTrue(cfg["host"])


class RequestTest(unittest.TestCase):
    good = {"type": "play", "url": "https://example.org/v", "page_url": "https://example.org/",
            "title": "t", "start": 1.5}

    def test_both_validators_accept_a_good_request(self):
        for validate in (client.validate_request, handoff.validate_request):
            self.assertEqual(validate(dict(self.good))["url"], "https://example.org/v")

    def test_both_validators_refuse_other_schemes(self):
        for validate in (client.validate_request, handoff.validate_request):
            for url in ("file:///etc/passwd", "javascript:alert(1)", "-oProxyCommand=x", ""):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    validate({**self.good, "url": url})

    def test_both_validators_refuse_bad_start(self):
        for validate in (client.validate_request, handoff.validate_request):
            for start in (-1, "3", True):
                with self.subTest(start=start), self.assertRaises(ValueError):
                    validate({**self.good, "start": start})

    def test_page_url_may_be_absent(self):
        for validate in (client.validate_request, handoff.validate_request):
            self.assertIsNone(validate({**self.good, "page_url": None})["page_url"])


class TemplateTest(unittest.TestCase):
    def test_fills_placeholders(self):
        out = client.fill_template(["mpv", "--title={title}", "{url}"],
                                   {"title": "A b", "url": "https://x/"})
        self.assertEqual(out, ["mpv", "--title=A b", "https://x/"])

    def test_drops_argument_without_value(self):
        out = client.fill_template(["mpv", "--start={start}", "{url}"],
                                   {"start": None, "url": "https://x/"})
        self.assertEqual(out, ["mpv", "https://x/"])

    def test_zero_start_is_dropped(self):
        values = client.player_values({"url": "https://x/", "page_url": None, "title": "", "start": 0.0})
        self.assertIsNone(values["start"])
        self.assertEqual(values["title"], "https://x/")


class RemoteTest(unittest.TestCase):
    def remote(self, **over):
        cfg = client.merge(client.DEFAULTS, {"host": "me@vm", **over})
        return client.Remote(cfg, "default")

    def test_remote_arguments_survive_the_remote_shell(self):
        r = self.remote()
        nasty = '{"url": "https://x/?a=1&b=$(id)", "title": "it\'s"}'
        line = r.command("exec", "default", "arbatrate-fetch", nasty)
        words = shlex.split(line)
        self.assertEqual(words[-1], nasty)
        self.assertEqual(words[-4:-1], ["exec", "default", "arbatrate-fetch"])

    def test_host_command_is_left_for_the_remote_shell(self):
        r = self.remote(host_command="~/bin/arbatrate-host")
        self.assertIn(" ~/bin/arbatrate-host ", r.command("doctor") + " ")

    def test_settings_travel_as_environment(self):
        r = self.remote(chromium={"flags": ["--force-dark-mode", "--lang=fr"]})
        words = shlex.split(r.command("run", "default"))
        self.assertEqual(words[0], "env")
        self.assertIn("ARBATRATE_CHROMIUM_FLAGS=--force-dark-mode --lang=fr", words)

    def test_no_host_is_a_config_error(self):
        with self.assertRaises(client.ConfigError):
            client.Remote(client.merge(client.DEFAULTS, {}), "default")


if __name__ == "__main__":
    unittest.main()
