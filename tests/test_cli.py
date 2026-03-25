"""
Smoke tests for the Cortex CLI (src/cortex/cli/main.py).

Strategy: the CLI parses sys.argv manually (no argparse). Tests patch sys.argv
and mock the async command coroutines so no database or network is needed.
"""
from __future__ import annotations

import io
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_main_with_argv(argv: list[str], capsys=None):
    """
    Set sys.argv to argv and call main().  Returns (stdout, exit_code).
    exit_code is None when main() returns normally, or the int passed to
    sys.exit() when it raises SystemExit.
    """
    from cortex.cli.main import main

    with patch.object(sys, "argv", argv):
        try:
            main()
            return capsys.readouterr().out if capsys else "", None
        except SystemExit as exc:
            out = capsys.readouterr().out if capsys else ""
            code = exc.code if isinstance(exc.code, int) else 1
            return out, code


# ---------------------------------------------------------------------------
# Parser / dispatch tests (no DB, no network)
# All async command functions are replaced with AsyncMock so that
# asyncio.run() completes instantly.
# ---------------------------------------------------------------------------

class TestCommandDispatch:
    """Verify that each token in sys.argv[1] routes to the right coroutine."""

    def _patch_cmd(self, func_name: str):
        """Return a context manager that replaces the named async function."""
        return patch(f"cortex.cli.main.{func_name}", new_callable=AsyncMock)

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    def test_parser_accepts_search_command(self):
        """'search <query>' dispatches to _cmd_search."""
        with self._patch_cmd("_cmd_search") as mock_search:
            with patch.object(sys, "argv", ["cortex", "search", "test query"]):
                from cortex.cli.main import main
                main()
        mock_search.assert_awaited_once()

    # ------------------------------------------------------------------
    # import --vault
    # ------------------------------------------------------------------
    def test_parser_accepts_import_vault(self):
        """'import --vault /path' dispatches to _cmd_import."""
        with self._patch_cmd("_cmd_import") as mock_import:
            with patch.object(sys, "argv", ["cortex", "import", "--vault", "/tmp/vault"]):
                from cortex.cli.main import main
                main()
        mock_import.assert_awaited_once()

    # ------------------------------------------------------------------
    # import-link
    # ------------------------------------------------------------------
    def test_parser_accepts_import_link(self):
        """'import-link <url>' dispatches to _cmd_import_link."""
        with self._patch_cmd("_cmd_import_link") as mock_link:
            with patch.object(sys, "argv", ["cortex", "import-link", "https://example.com"]):
                from cortex.cli.main import main
                main()
        mock_link.assert_awaited_once()

    # ------------------------------------------------------------------
    # import-file
    # ------------------------------------------------------------------
    def test_parser_accepts_import_file(self):
        """'import-file /path/to/file.pdf' dispatches to _cmd_import_file."""
        with self._patch_cmd("_cmd_import_file") as mock_file:
            with patch.object(sys, "argv", ["cortex", "import-file", "/tmp/doc.pdf"]):
                from cortex.cli.main import main
                main()
        mock_file.assert_awaited_once()

    # ------------------------------------------------------------------
    # annotate
    # ------------------------------------------------------------------
    def test_parser_accepts_annotate(self):
        """'annotate <id> <text>' dispatches to _cmd_annotate."""
        with self._patch_cmd("_cmd_annotate") as mock_ann:
            with patch.object(sys, "argv", ["cortex", "annotate", "some-event-id", "agree"]):
                from cortex.cli.main import main
                main()
        mock_ann.assert_awaited_once()

    # ------------------------------------------------------------------
    # notifications
    # ------------------------------------------------------------------
    def test_parser_accepts_notifications(self):
        """'notifications' dispatches to _cmd_notifications."""
        with self._patch_cmd("_cmd_notifications") as mock_notif:
            with patch.object(sys, "argv", ["cortex", "notifications"]):
                from cortex.cli.main import main
                main()
        mock_notif.assert_awaited_once()

    # ------------------------------------------------------------------
    # maintain classification  (subcommand forwarded via sys.argv[2])
    # ------------------------------------------------------------------
    def test_parser_accepts_maintain_classification(self):
        """'maintain classification' dispatches to _cmd_maintain."""
        with self._patch_cmd("_cmd_maintain") as mock_maint:
            with patch.object(sys, "argv", ["cortex", "maintain", "classification"]):
                from cortex.cli.main import main
                main()
        mock_maint.assert_awaited_once()

    # ------------------------------------------------------------------
    # serve  (synchronous, uses uvicorn)
    # ------------------------------------------------------------------
    def test_parser_accepts_serve(self):
        """'serve' dispatches to _cmd_serve without crashing."""
        mock_serve = MagicMock()
        with patch("cortex.cli.main._cmd_serve", mock_serve):
            with patch.object(sys, "argv", ["cortex", "serve"]):
                from cortex.cli.main import main
                main()
        mock_serve.assert_called_once()

    # ------------------------------------------------------------------
    # Additional commands present in the dispatcher
    # ------------------------------------------------------------------
    def test_parser_accepts_sync(self):
        """'sync --vault /path' dispatches to _cmd_sync."""
        with self._patch_cmd("_cmd_sync") as mock_sync:
            with patch.object(sys, "argv", ["cortex", "sync", "--vault", "/tmp/vault"]):
                from cortex.cli.main import main
                main()
        mock_sync.assert_awaited_once()

    def test_parser_accepts_thesis(self):
        """'thesis' dispatches to _cmd_thesis."""
        with self._patch_cmd("_cmd_thesis") as mock_thesis:
            with patch.object(sys, "argv", ["cortex", "thesis"]):
                from cortex.cli.main import main
                main()
        mock_thesis.assert_awaited_once()

    def test_parser_accepts_stats(self):
        """'stats' dispatches to _cmd_stats."""
        with self._patch_cmd("_cmd_stats") as mock_stats:
            with patch.object(sys, "argv", ["cortex", "stats"]):
                from cortex.cli.main import main
                main()
        mock_stats.assert_awaited_once()

    def test_parser_accepts_stale(self):
        """'stale' dispatches to _cmd_stale."""
        with self._patch_cmd("_cmd_stale") as mock_stale:
            with patch.object(sys, "argv", ["cortex", "stale"]):
                from cortex.cli.main import main
                main()
        mock_stale.assert_awaited_once()

    def test_parser_accepts_digest(self):
        """'digest' dispatches to _cmd_digest."""
        with self._patch_cmd("_cmd_digest") as mock_digest:
            with patch.object(sys, "argv", ["cortex", "digest"]):
                from cortex.cli.main import main
                main()
        mock_digest.assert_awaited_once()


# ---------------------------------------------------------------------------
# Help output tests
# ---------------------------------------------------------------------------

class TestHelpOutput:
    """_print_help() must mention every documented command."""

    EXPECTED_COMMANDS = [
        "search",
        "import",
        "sync",
        "thesis",
        "stats",
        "stale",
        "serve",
        "digest",
        "maintain",
        "import-link",
        "import-file",
        "annotate",
        "notifications",
    ]

    def _capture_help(self) -> str:
        """Call _print_help() and return what it printed."""
        from cortex.cli.main import _print_help

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _print_help()
        return buf.getvalue()

    def test_main_help_contains_all_commands(self):
        """Help text mentions every command registered in main()."""
        output = self._capture_help()
        for cmd in self.EXPECTED_COMMANDS:
            assert cmd in output, f"Help output is missing command: {cmd!r}"

    def test_help_flag_does_not_crash(self, capsys):
        """Passing --help to main() prints help and returns without crashing."""
        with patch.object(sys, "argv", ["cortex", "--help"]):
            from cortex.cli.main import main
            main()  # must not raise

        out = capsys.readouterr().out
        assert "cortex" in out.lower() or "commands" in out.lower()

    def test_help_shortflag_does_not_crash(self, capsys):
        """-h is also handled by main()."""
        with patch.object(sys, "argv", ["cortex", "-h"]):
            from cortex.cli.main import main
            main()

        out = capsys.readouterr().out
        assert len(out) > 0, "Expected some help output for -h"

    def test_no_args_prints_help(self, capsys):
        """Calling cortex with no arguments prints help text."""
        with patch.object(sys, "argv", ["cortex"]):
            from cortex.cli.main import main
            main()

        out = capsys.readouterr().out
        assert len(out) > 0, "Expected help output when no arguments given"

    def test_unknown_command_exits_nonzero(self, capsys):
        """An unknown command prints an error message and exits with code 1."""
        with patch.object(sys, "argv", ["cortex", "does-not-exist"]):
            from cortex.cli.main import main
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "does-not-exist" in out


# ---------------------------------------------------------------------------
# Import / module-level smoke test
# ---------------------------------------------------------------------------

class TestImports:
    """Verify that key modules can be imported without side effects."""

    def test_cli_main_importable(self):
        """cortex.cli.main can be imported cleanly."""
        import cortex.cli.main  # noqa: F401

    def test_create_app_importable(self):
        """cortex.api.main.create_app can be imported without crashing."""
        from cortex.api.main import create_app  # noqa: F401
        assert callable(create_app)

    def test_main_function_exists(self):
        """The CLI exposes a callable main() entry point."""
        from cortex.cli.main import main
        assert callable(main)

    def test_print_help_exists(self):
        """_print_help() is a callable in the module."""
        from cortex.cli.main import _print_help
        assert callable(_print_help)

    def test_load_config_exists(self):
        """load_config() is importable and callable."""
        from cortex.cli.main import load_config
        assert callable(load_config)