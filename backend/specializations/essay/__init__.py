from app.plugin_registry import register_specialization

register_specialization(
    domain="essay",
    prompt_file=__file__,
    tools=[],
)
