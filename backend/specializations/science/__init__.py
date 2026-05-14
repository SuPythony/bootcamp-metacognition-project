from app.plugin_registry import register_specialization

register_specialization(
    domain="science",
    prompt_file=__file__,
    tools=["graph", "data_table"],
)
