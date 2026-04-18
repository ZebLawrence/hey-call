def test_build_system_prompt_substitutes_goal_and_context():
    """Both placeholders are replaced; neither template marker remains."""
    from call import build_system_prompt
    result = build_system_prompt("ask the time", "they sound grumpy, be patient")
    assert "ask the time" in result
    assert "they sound grumpy, be patient" in result
    assert "{{GOAL}}" not in result
    assert "{{CONTEXT}}" not in result


def test_build_system_prompt_handles_empty_context():
    """Empty context is replaced with a neutral marker, not the raw placeholder."""
    from call import build_system_prompt
    result = build_system_prompt("ask the time")
    assert "ask the time" in result
    assert "{{CONTEXT}}" not in result
    assert "(none provided)" in result


def test_build_system_prompt_handles_whitespace_only_context():
    """Whitespace-only context is treated as empty."""
    from call import build_system_prompt
    result = build_system_prompt("ask the time", "   \n  ")
    assert "{{CONTEXT}}" not in result
    assert "(none provided)" in result
