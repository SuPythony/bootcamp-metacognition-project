from app.plugin_registry import register_specialization

register_specialization(
    domain="math",
    prompt_file=__file__,
    tools=["algebra", "graph"],
)
