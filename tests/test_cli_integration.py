"""
CLI-level tests for docmap.cli.

These invoke `python -m docmap.cli` via subprocess to cover the CLI
grammar, guardrail refusals, and exit codes end to end.

The `run_cli` and `sample_project` fixtures live in conftest.py.
"""

# ---------- documentation ----------


def test_cli_bare_prints_banner(run_cli):
    result = run_cli([])
    assert result.returncode == 0
    assert "docmap print PATH" in result.stdout
    assert result.stderr == ""


def test_cli_bare_command_word_prints_the_same_banner(run_cli):
    bare = run_cli([])
    word = run_cli(["print"])
    assert word.returncode == 0
    assert word.stdout == bare.stdout


def test_cli_bare_with_piped_stdin_still_prints_banner(run_cli):
    result = run_cli([], input_text="")
    assert result.returncode == 0
    assert "docmap print PATH" in result.stdout


# ---------- grammar ----------


def test_cli_print_without_path_is_usage_error(run_cli):
    result = run_cli(["print", "--include-private"])
    assert result.returncode == 1
    assert "print needs PATH" in result.stderr
    assert "Usage: docmap print" in result.stderr
    assert result.stdout == ""


def test_cli_flags_follow_path_in_any_order(run_cli, sample_project):
    result = run_cli(["print", str(sample_project), "--force", "--include-private"])
    assert result.returncode == 0
    assert "mod.py:" in result.stdout


def test_cli_flag_before_path_is_usage_error(run_cli, sample_project):
    result = run_cli(["print", "--include-private", str(sample_project)])
    assert result.returncode == 1
    assert "print needs PATH" in result.stderr


def test_cli_second_positional_is_usage_error(run_cli, sample_project):
    result = run_cli(["print", str(sample_project), "extra"])
    assert result.returncode == 1
    assert "nothing after PATH" in result.stderr


def test_cli_nonexistent_path_is_error(run_cli, tmp_path):
    result = run_cli(["print", str(tmp_path / "nope")])
    assert result.returncode == 1
    assert "is not a directory" in result.stderr
    assert result.stderr.startswith("docmap: ")


def test_cli_unknown_flag_is_argparse_error(run_cli, sample_project):
    result = run_cli(["print", str(sample_project), "--nope"])
    assert result.returncode == 2


def test_cli_old_src_root_grammar_is_argparse_error(run_cli, sample_project):
    result = run_cli(["--src-root", str(sample_project)])
    assert result.returncode == 2


def test_cli_out_flag_is_gone(run_cli, sample_project):
    out_file = sample_project / "manifest.yaml"
    result = run_cli(["print", str(sample_project), "--out", str(out_file)])
    assert result.returncode == 2
    assert not out_file.exists()


# ---------- guardrails ----------


def test_cli_refuses_system_root_without_force(run_cli, tmp_path):
    for name in ("bin", "etc", "usr", "lib"):
        (tmp_path / name).mkdir()
    result = run_cli(["print", str(tmp_path)])
    assert result.returncode == 1
    assert "docmap: refusing to walk" in result.stderr
    assert "--force" in result.stderr


def test_cli_force_overrides_system_root_sniff(run_cli, tmp_path):
    for name in ("bin", "etc", "usr", "lib"):
        (tmp_path / name).mkdir()
    result = run_cli(["print", str(tmp_path), "--force"])
    assert result.returncode == 0


# ---------- output ----------


def test_cli_prints_map_to_stdout(run_cli, sample_project):
    result = run_cli(["print", str(sample_project)])
    assert result.returncode == 0
    assert "mod.py:" in result.stdout
    assert "Say hello." in result.stdout
