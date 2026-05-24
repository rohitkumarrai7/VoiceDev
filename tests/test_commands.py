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

    def test_exact_match_cancel_that(self):
        result = self.router.route("cancel that")
        assert result is not None
        assert result[1] == "/undo"

    def test_exact_match_revert_that(self):
        result = self.router.route("revert that")
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

    def test_exact_match_quit(self):
        result = self.router.route("quit")
        assert result is not None
        assert result[1] == "shutdown"

    def test_exact_match_hands_free(self):
        result = self.router.route("switch to hands free")
        assert result is not None
        assert result[1] == "mode_hands_free"

    def test_exact_match_go_hands_free(self):
        result = self.router.route("go hands free")
        assert result is not None
        assert result[1] == "mode_hands_free"

    def test_exact_match_commit_changes(self):
        result = self.router.route("commit changes")
        assert result is not None
        assert result[1] == "/commit"

    def test_exact_match_architect_mode(self):
        result = self.router.route("architect mode")
        assert result is not None
        assert result[1] == "/chat-mode architect"

    def test_exact_match_code_mode(self):
        result = self.router.route("code mode")
        assert result is not None
        assert result[1] == "/chat-mode code"

    def test_exact_match_ask_mode(self):
        result = self.router.route("ask mode")
        assert result is not None
        assert result[1] == "/chat-mode ask"

    def test_exact_match_list_files(self):
        result = self.router.route("list files")
        assert result is not None
        assert result[1] == "list_files"

    def test_exact_match_show_status(self):
        result = self.router.route("show status")
        assert result is not None
        assert result[1] == "show_status"

    def test_exact_match_show_history(self):
        result = self.router.route("show history")
        assert result is not None
        assert result[1] == "show_history"

    def test_exact_match_help(self):
        result = self.router.route("help me")
        assert result is not None
        assert result[1] == "help"

    def test_exact_match_git_status(self):
        result = self.router.route("git status")
        assert result is not None
        assert result[1] == "/git status"

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

    def test_add_file_prefix_command(self):
        result = self.router.route("add file main.py")
        assert result is not None
        phrase, action = result
        assert action == "/add main.py"

    def test_drop_file_prefix_command(self):
        result = self.router.route("drop file utils.py")
        assert result is not None
        assert result[1] == "/drop utils.py"

    def test_run_command_prefix(self):
        result = self.router.route("run command ls -la")
        assert result is not None
        assert result[1] == "/run ls -la"

    def test_custom_command(self):
        self.router.add_command("deploy now", "/run deploy.sh")
        result = self.router.route("deploy now")
        assert result is not None
        assert result[1] == "/run deploy.sh"

    def test_remove_custom_command(self):
        self.router.add_command("deploy now", "/run deploy.sh")
        self.router.remove_command("deploy now")
        result = self.router.route("deploy now")
        assert result is None or result[1] != "/run deploy.sh"

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

    def test_history_tracking(self):
        self.router.route("undo that")
        self.router.route("show diff")
        self.router.route("hello world")
        assert len(self.router.history) == 3
        assert "undo that" in self.router.history
        assert "show diff" in self.router.history

    def test_list_project_files(self):
        result = CommandRouter.list_project_files()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_help_text(self):
        result = CommandRouter.get_help_text()
        assert "Voice Commands" in result
        assert "undo that" in result
        assert "add file" in result
