"""
CLI-level tests for docmap.cli.

These invoke `python -m docmap.cli` via subprocess to cover the CLI
grammar, guardrail refusals, file output, and exit codes end to end.

The `run_cli` and `sample_project` fixtures live in conftest.py.
"""

# ---------- grammar ----------


def test_cli_bare_with_piped_stdin_is_usage_error(run_cli):
    result = run_cli([], input_text="")
    assert result.returncode == 1
    assert "takes no piped input" in result.stderr
    assert "Usage: docmap" in result.stderr
    assert result.stdout == ""


def test_cli_flags_without_root_is_usage_error(run_cli):
    result = run_cli(["--include-private"], input_text="")
    assert result.returncode == 1
    assert "missing ROOT" in result.stderr


def test_cli_root_must_be_last_argument(run_cli, sample_project):
    result = run_cli([str(sample_project), "--include-private"], input_text="")
    assert result.returncode == 1
    assert "must be the last argument" in result.stderr
    assert "Usage: docmap" in result.stderr


def test_cli_flags_first_root_last_is_accepted(run_cli, sample_project):
    result = run_cli(["--include-private", str(sample_project)], input_text="")
    assert result.returncode == 0
    assert "mod.py:" in result.stdout


def test_cli_nonexistent_root_is_error(run_cli, tmp_path):
    result = run_cli([str(tmp_path / "nope")], input_text="")
    assert result.returncode == 1
    assert "is not a directory" in result.stderr
    assert result.stderr.startswith("docmap: ")


def test_cli_unknown_flag_is_argparse_error(run_cli, sample_project):
    result = run_cli(["--nope", str(sample_project)], input_text="")
    assert result.returncode == 2


# ---------- guardrails ----------


def test_cli_refuses_system_root_without_force(run_cli, tmp_path):
    for name in ("bin", "etc", "usr", "lib"):
        (tmp_path / name).mkdir()
    result = run_cli([str(tmp_path)], input_text="")
    assert result.returncode == 1
    assert "docmap: refusing to walk" in result.stderr
    assert "--force" in result.stderr


def test_cli_force_overrides_system_root_sniff(run_cli, tmp_path):
    for name in ("bin", "etc", "usr", "lib"):
        (tmp_path / name).mkdir()
    result = run_cli(["--force", str(tmp_path)], input_text="")
    assert result.returncode == 0


# ---------- output ----------


def test_cli_prints_map_to_stdout(run_cli, sample_project):
    result = run_cli([str(sample_project)], input_text="")
    assert result.returncode == 0
    assert "mod.py:" in result.stdout
    assert "Say hello." in result.stdout


def test_cli_writes_out_file(run_cli, sample_project):
    out_file = sample_project / "manifest.yaml"
    result = run_cli(["--out", str(out_file), str(sample_project)], input_text="")
    assert result.returncode == 0
    assert out_file.exists()
    assert "mod.py:" in out_file.read_text()
