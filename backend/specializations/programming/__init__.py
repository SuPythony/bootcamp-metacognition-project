from app.plugin_registry import register_specialization

register_specialization(
    domain="programming",
    prompt_file=__file__,
    tools=["code_runner"],
)
