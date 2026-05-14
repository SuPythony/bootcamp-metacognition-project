from app.plugin_registry import register_specialization

register_specialization(
    domain="general",
    prompt_file=__file__,
    tools=[],
)
