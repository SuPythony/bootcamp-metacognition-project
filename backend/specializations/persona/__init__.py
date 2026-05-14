from app.plugin_registry import register_specialization

register_specialization(
    domain="persona",
    prompt_file=__file__,
    tools=[],
)
