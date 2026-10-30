"""The rename contract's mapping back (ROADMAP §3.4): what ceesafec prints under CeeSafe's names, with Nova's names
put back, so it can be compared with novac's output byte for byte. The pairs are applied in order, longest first."""

MAP_BACK = ((b"ceesafe.toml", b"nova.toml"), (b"ceesafe.lock", b"nova.lock"), (b"CEESAFE_HOME", b"NOVA_HOME"),
            (b"ceesafec", b"novac"), (b"<file.cee>", b"<file.nova>"), (b".cee", b".nova"))


def map_back(output):
    for new, old in MAP_BACK:
        output = output.replace(new, old)
    return output
