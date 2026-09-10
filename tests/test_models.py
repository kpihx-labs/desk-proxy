"""Envelope shape — meta carries the audit trail, data stays pure."""

from desk_proxy.models import OutputMeta, ok, rejected


def test_default_meta() -> None:
    assert OutputMeta().model_dump() == {
        "status": "ok",
        "comment": "",
        "edited": False,
    }


def test_ok_envelope() -> None:
    env = ok({"path": "/tmp/desk-proxy-shots/a.png"})
    assert env["meta"]["status"] == "ok"
    assert env["data"] == {"path": "/tmp/desk-proxy-shots/a.png"}


def test_rejected_envelope() -> None:
    env = rejected("not now", edited=True)
    assert env["meta"]["status"] == "rejected"
    assert env["meta"]["edited"] is True
    assert env["meta"]["comment"] == "not now"
    assert env["data"] is None


def test_ok_with_approved_status() -> None:
    env = ok({"x": 1}, status="approved", comment="lgtm", edited=False)
    assert env["meta"]["status"] == "approved"
    assert env["meta"]["comment"] == "lgtm"
    assert env["data"] == {"x": 1}
