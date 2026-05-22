import pytest

from voicedev.commands.router import CommandRouter


class TestCommandRouter:
    def setup_method(self):
        self.router = CommandRouter(match_threshold=75)

    def test_exact_match_clear_context(self):
        result = self.router.route("clear context")
        assert result is not None
        phrase, action = result
        assert action == "/clear"

    def test_exact_match_run_tests(self):
        result = self.router.route("run tests")
        assert result is not None
        assert result[1] == "/run pytest"

    def test_exact_match_undo(self):
        result = self.router.route("undo that")
        assert result is not None
        assert result[1] == "/undo"

    def test_exact_match_show_diff(self):
        result = self.router.route("show diff")
        assert result is not None
        assert result[1] == "/diff"

    def test_exact_match_stop_listening(self):
        result = self.router.route("stop listening")
        assert result is not None
        assert result[1] == "pause"

    def test_exact_match_start_listening(self):
        result = self.router.route("start listening")
        assert result is not None
        assert result[1] == "resume"

    def test_exact_match_switch_continuous(self):
        result = self.router.route("switch to continuous")
        assert result is not None
        assert result[1] == "mode_continuous"

    def test_exact_match_switch_manual(self):
        result = self.router.route("switch to manual")
        assert result is not None
        assert result[1] == "mode_manual"

    def test_exact_match_exit(self):
        result = self.router.route("exit")
        assert result is not None
        assert result[1] == "shutdown"

    def test_fuzzy_match_typo(self):
        result = self.router.route("undo tht")
        assert result is not None
        assert result[1] == "/undo"

    def test_fuzzy_match_clear_contxt(self):
        result = self.router.route("clear contxt")
        assert result is not None
        assert result[1] == "/clear"

    def test_no_match_normal_text(self):
        result = self.router.route("create a python function that reads a csv")
        assert result is None

    def test_empty_string(self):
        result = self.router.route("")
        assert result is None

    def test_whitespace(self):
        result = self.router.route("   ")
        assert result is None

    def test_add_file_command(self):
        result = self.router.route("add file main.py")
        assert result is not None
        phrase, action = result
        assert "/add main.py" in action

    def test_custom_command(self):
        self.router.add_command("commit changes", "/commit")
        result = self.router.route("commit changes")
        assert result is not None
        assert result[1] == "/commit"

    def test_remove_custom_command(self):
        self.router.add_command("commit changes", "/commit")
        self.router.remove_command("commit changes")
        result = self.router.route("commit changes")
        assert result is None or result[1] != "/commit"

    def test_yes_command(self):
        result = self.router.route("yes")
        assert result is not None
        assert result[1] == "Y"

    def test_no_command(self):
        result = self.router.route("no")
        assert result is not None
        assert result[1] == "N"

    def test_accept_command(self):
        result = self.router.route("accept")
        assert result is not None
        assert result[1] == "Y"

    def test_reject_command(self):
        result = self.router.route("reject")
        assert result is not None
        assert result[1] == "N"
