import json
from urllib.request import urlopen


URL = (
    "http://127.0.0.1:9000/"
    "api/v1/twin/state"
)


with urlopen(
    URL,
    timeout=3,
) as response:
    state = json.load(response)


assert state["quality"]["valid"] is True


for controller in state[
    "controllers"
]:
    assert (
        controller[
            "safe_capacity_pps"
        ] > 0
    )

    assert (
        controller[
            "utilization"
        ] >= 0
    )

    assert (
        controller[
            "collection_latency_ms"
        ] >= 0
    )


print(
    "WEEK6 TWIN STATE: PASS"
)
