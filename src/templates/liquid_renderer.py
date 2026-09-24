from liquid import Environment

_ENV = Environment()


def render_liquid(template_source: str, rendering_data: dict) -> str:
    template = _ENV.from_string(template_source)
    return template.render(data=rendering_data)


def unresolved_liquid_tokens(html: str) -> list[str]:
    leftovers = []
    for token in ("{{", "}}", "{%", "%}"):
        if token in html:
            leftovers.append(token)
    return leftovers
