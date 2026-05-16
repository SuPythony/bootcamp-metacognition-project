"""Tests for the folder-scanning plugin loader."""

from __future__ import annotations

import json

import pytest


def test_load_specializations_finds_all_v1_domains(loaded_registry):
    domains = set(loaded_registry.list_domains())
    # Six folders on disk: five user-facing + one internal (persona).
    assert domains == {"math", "programming", "essay", "science", "general", "persona"}


def test_get_specializations_excludes_internal(loaded_registry):
    public = loaded_registry.get_specializations()
    public_domains = {entry["domain"] for entry in public}
    assert "persona" not in public_domains
    assert public_domains == {"math", "programming", "essay", "science", "general"}


def test_is_internal(loaded_registry):
    assert loaded_registry.is_internal("persona") is True
    assert loaded_registry.is_internal("math") is False
    # Unknown domains are not internal (defensive default).
    assert loaded_registry.is_internal("nonexistent") is False


def test_get_prompt_concatenates_base_and_domain(loaded_registry):
    prompt = loaded_registry.get_prompt("math")
    # Socratic base contains a recognizable marker.
    assert "Socratic tutor" in prompt
    # Math domain prompt has a known string (tool name declaration).
    assert "symbolic algebra" in prompt
    # The base comes first.
    assert prompt.index("Socratic tutor") < prompt.index("symbolic algebra")


def test_get_prompt_unknown_domain_raises(loaded_registry):
    with pytest.raises(KeyError):
        loaded_registry.get_prompt("nonexistent")


def test_get_manifest_returns_parsed_json(loaded_registry):
    manifest = loaded_registry.get_manifest("math")
    assert manifest["domain"] == "math"
    assert {t["name"] for t in manifest["tools"]} == {"algebra", "graph"}
    for tool in manifest["tools"]:
        assert tool["execution"] in {"backend", "frontend"}


def test_programming_code_runner_is_frontend(loaded_registry):
    """After PR #2, code_runner is a frontend Pyodide tool."""
    manifest = loaded_registry.get_manifest("programming")
    code_runner = next(t for t in manifest["tools"] if t["name"] == "code_runner")
    assert code_runner["execution"] == "frontend"
    assert code_runner["frontend_handler"] == "PyodideRunner"


def test_duplicate_registration_rejected(loaded_registry):
    """Registering the same domain twice raises."""
    # The loader has already imported each spec. A second register call on
    # the same domain should fail.
    with pytest.raises(ValueError, match="already registered"):
        loaded_registry.register_specialization(
            domain="math", prompt_file=str(loaded_registry.SPECIALIZATIONS_DIR / "math" / "__init__.py"), tools=["algebra", "graph"]
        )


def test_register_with_mismatched_tools_rejected(tmp_path, monkeypatch):
    """A spec whose __init__.py declares tools that don't match its manifest
    must fail loud, not silently."""
    from app import plugin_registry

    # Build a minimal fake specialization in a temp dir.
    fake = tmp_path / "fakespec"
    fake.mkdir()
    (fake / "__init__.py").write_text("# fake")
    (fake / "prompt.txt").write_text("Fake prompt.")
    (fake / "manifest.json").write_text(
        json.dumps({"domain": "fakespec", "tools": [{"name": "real_tool", "execution": "backend"}]})
    )

    with pytest.raises(ValueError, match="do not match"):
        plugin_registry.register_specialization(
            domain="fakespec",
            prompt_file=str(fake / "__init__.py"),
            tools=["different_tool"],  # mismatch
        )


def test_register_with_missing_execution_field_rejected(tmp_path):
    from app import plugin_registry

    fake = tmp_path / "fakespec2"
    fake.mkdir()
    (fake / "__init__.py").write_text("# fake")
    (fake / "prompt.txt").write_text("Fake prompt.")
    (fake / "manifest.json").write_text(
        json.dumps(
            {"domain": "fakespec2", "tools": [{"name": "tool_no_execution"}]}
        )
    )

    with pytest.raises(ValueError, match="execution"):
        plugin_registry.register_specialization(
            domain="fakespec2",
            prompt_file=str(fake / "__init__.py"),
            tools=["tool_no_execution"],
        )


def test_frontend_tool_must_declare_handler(tmp_path):
    from app import plugin_registry

    fake = tmp_path / "fakespec3"
    fake.mkdir()
    (fake / "__init__.py").write_text("# fake")
    (fake / "prompt.txt").write_text("Fake prompt.")
    (fake / "manifest.json").write_text(
        json.dumps(
            {
                "domain": "fakespec3",
                "tools": [{"name": "frontend_tool_no_handler", "execution": "frontend"}],
            }
        )
    )

    with pytest.raises(ValueError, match="frontend_handler"):
        plugin_registry.register_specialization(
            domain="fakespec3",
            prompt_file=str(fake / "__init__.py"),
            tools=["frontend_tool_no_handler"],
        )


def test_dispatch_tool_frontend_returns_sentinel(loaded_registry):
    """Frontend tools must not be executed by the backend — dispatch returns
    a sentinel the chat layer surfaces to the client."""
    # Use a fake session — dispatch shouldn't actually invoke anything.
    result = loaded_registry.dispatch_tool(
        "programming", "code_runner", {"code": "print(1)"}, session=None
    )
    assert result["execution"] == "frontend"
    assert result["name"] == "code_runner"
    assert result["frontend_handler"] == "PyodideRunner"
    assert result["args"] == {"code": "print(1)"}


def test_dispatch_unknown_tool_raises(loaded_registry):
    with pytest.raises(KeyError, match="not registered"):
        loaded_registry.dispatch_tool("math", "nonexistent_tool", {}, session=None)


def test_dispatch_unknown_domain_raises(loaded_registry):
    with pytest.raises(KeyError, match="Unknown domain"):
        loaded_registry.dispatch_tool("nope", "algebra", {}, session=None)


def test_dispatch_backend_tool_imports_and_invokes(loaded_registry, monkeypatch):
    """Backend tool: dispatch imports specializations.<domain>.tools.<name>
    and calls its run(args, session) function.

    We use the real math spec's manifest (which declares an `algebra` tool
    with execution=backend) and inject a fake module into sys.modules so
    importlib resolves it without touching the on-disk stub.
    """
    import sys
    import types

    fake = types.ModuleType("specializations.math.tools.algebra")

    def fake_run(args, session):
        return {"result": args, "display_data": {"steps": [], "final": str(args)}}

    fake.run = fake_run
    monkeypatch.setitem(sys.modules, "specializations.math.tools.algebra", fake)

    result = loaded_registry.dispatch_tool(
        "math", "algebra", {"expression": "x+1", "operation": "simplify"}, session=None
    )

    assert result["execution"] == "backend"
    assert result["name"] == "algebra"
    assert result["result"] == {"expression": "x+1", "operation": "simplify"}
    assert result["ui_component"] == "AlgebraSteps"


def test_dispatch_backend_tool_requires_run_function(loaded_registry, monkeypatch):
    """Backend tool module without a run() function raises clearly."""
    import sys
    import types

    fake = types.ModuleType("specializations.math.tools.algebra")
    # No `run` attribute.
    monkeypatch.setitem(sys.modules, "specializations.math.tools.algebra", fake)

    with pytest.raises(RuntimeError, match="run\\(\\)"):
        loaded_registry.dispatch_tool("math", "algebra", {}, session=None)
