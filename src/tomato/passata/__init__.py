import zmq


def component(
    *,
    port: int,
    context: zmq.Context,
    name: str,
    **_: dict,
) -> Reply:
    pass