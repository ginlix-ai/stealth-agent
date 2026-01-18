from src.server.models.chat import (
    HITLDecision,
    HITLResponse,
    serialize_hitl_response_map,
    summarize_hitl_response_map,
)


def test_serialize_hitl_response_map_converts_pydantic_models() -> None:
    hitl_response = {
        "interrupt-1": HITLResponse(decisions=[HITLDecision(type="approve", message=None)])
    }

    serialized = serialize_hitl_response_map(hitl_response)

    assert serialized == {
        "interrupt-1": {
            "decisions": [
                {
                    "type": "approve",
                    "message": None,
                }
            ]
        }
    }


def test_serialize_hitl_response_map_passes_through_dict_values() -> None:
    hitl_response = {"interrupt-1": {"decisions": [{"type": "approve"}]}}

    serialized = serialize_hitl_response_map(hitl_response)

    assert serialized == {"interrupt-1": {"decisions": [{"type": "approve"}]}}


def test_summarize_hitl_response_map_all_approved() -> None:
    hitl_response = {
        "interrupt-1": HITLResponse(decisions=[HITLDecision(type="approve", message=None)]),
        "interrupt-2": {"decisions": [{"type": "approve"}]},
    }

    summary = summarize_hitl_response_map(hitl_response)

    assert summary == {
        "feedback_action": "APPROVED",
        "content": "",
        "interrupt_ids": ["interrupt-1", "interrupt-2"],
    }


def test_summarize_hitl_response_map_declined_with_message() -> None:
    hitl_response = {
        "interrupt-1": HITLResponse(
            decisions=[HITLDecision(type="reject", message="please change X")]
        )
    }

    summary = summarize_hitl_response_map(hitl_response)

    assert summary == {
        "feedback_action": "DECLINED",
        "content": "please change X",
        "interrupt_ids": ["interrupt-1"],
    }


def test_summarize_hitl_response_map_declined_without_message() -> None:
    hitl_response = {"interrupt-1": {"decisions": [{"type": "reject"}]}}

    summary = summarize_hitl_response_map(hitl_response)

    assert summary == {
        "feedback_action": "DECLINED",
        "content": "",
        "interrupt_ids": ["interrupt-1"],
    }
