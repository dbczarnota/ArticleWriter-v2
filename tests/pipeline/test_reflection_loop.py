def test_reflection_config_defaults():
    from agents._base.config import ReflectionAgentConfig
    cfg = ReflectionAgentConfig()
    assert cfg.max_rounds == 1
