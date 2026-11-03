from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import demo


def response(data, status=200):
    return SimpleNamespace(status_code=status, json=lambda: data, raise_for_status=lambda: None)


def occupy_port(monkeypatch):
    monkeypatch.setattr(demo.socket, "create_connection", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(
        demo.subprocess,
        "Popen",
        Mock(side_effect=AssertionError("Must not replace an existing server")),
    )


def test_reuses_existing_api_without_starting_or_stopping_another_process(monkeypatch):
    occupy_port(monkeypatch)
    server = demo.DemoServer(8000)
    server.session = Mock()
    server.session.get.side_effect = [
        response({"name": "Financial News Sentiment Analyzer", "model": "ProsusAI/finbert"}),
        response({"model_ready": True}),
    ]
    server.start()
    server.close()
    assert server.process is None
    server.session.close.assert_called_once()


def test_refuses_a_port_owned_by_an_unrelated_application(monkeypatch):
    occupy_port(monkeypatch)
    server = demo.DemoServer(8000)
    server.session = Mock()
    server.session.get.return_value = response({"name": "Another app", "model": "something else"})
    with pytest.raises(RuntimeError, match="ứng dụng khác"):
        server.start()
    assert server.process is None


@pytest.mark.parametrize("keep_server", [False, True])
def test_only_owned_process_is_stopped_unless_explicitly_kept(monkeypatch, keep_server):
    server = demo.DemoServer(8000)
    process = Mock()
    process.pid = 12345
    process.poll.return_value = None
    server.process = process
    terminate_tree = Mock()
    monkeypatch.setattr(demo.subprocess, "run", terminate_tree)
    server.close(keep_server=keep_server)
    if demo.os.name == "nt":
        assert terminate_tree.call_count == (0 if keep_server else 1)
        if not keep_server:
            assert terminate_tree.call_args.args[0] == ["taskkill", "/PID", "12345", "/T", "/F"]
    else:
        assert process.terminate.call_count == (0 if keep_server else 1)


def test_url_fallback_uses_a_second_real_request(monkeypatch):
    walkthrough = demo.Walkthrough(SimpleNamespace())
    call = Mock(side_effect=[RuntimeError("HTTP 502"), {"label": "neutral"}])
    monkeypatch.setattr(walkthrough, "call", call)
    walkthrough.scene(6)
    assert [item.args for item in call.call_args_list] == [
        ("/predict", {"url": demo.NVIDIA_URL}),
        ("/predict", {"url": demo.FED_URL}),
    ]


def test_http_failure_is_recorded_and_never_accepted_as_a_prediction():
    session = Mock()
    session.request.return_value = response({"detail": "Download failed"}, status=502)
    walkthrough = demo.Walkthrough(
        SimpleNamespace(session=session, base_url="http://127.0.0.1:8000")
    )
    with pytest.raises(RuntimeError, match="nhận 502"):
        walkthrough.call("/predict", {"url": demo.NVIDIA_URL})
    assert walkthrough.records[0]["status_code"] == 502


def test_expected_validation_error_is_a_successful_demo_step():
    session = Mock()
    session.request.return_value = response({"detail": "Empty text"}, status=422)
    walkthrough = demo.Walkthrough(
        SimpleNamespace(session=session, base_url="http://127.0.0.1:8000")
    )
    assert walkthrough.call("/predict", {"text": " "}, expected_status=422) == {
        "detail": "Empty text"
    }


def test_timeline_includes_request_time_and_keeps_270_second_budget(monkeypatch, tmp_path):
    clock = SimpleNamespace(now=0.0)
    server = SimpleNamespace(
        base_url="http://127.0.0.1:8000", process=None, start=Mock(), close=Mock()
    )
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    monkeypatch.setattr(demo, "DemoServer", lambda port: server)
    monkeypatch.setattr(demo.time, "monotonic", lambda: clock.now)

    def advance(seconds):
        clock.now += seconds

    monkeypatch.setattr(demo.time, "sleep", advance)
    # A slow first scene overruns its slot; later waits must shorten to compensate.
    monkeypatch.setattr(
        demo.Walkthrough, "scene", lambda self, index: advance(40 if index == 0 else 8)
    )
    args = SimpleNamespace(port=8000, fast=False, auto_start=True, no_clear=True, keep_server=False)
    assert demo.run(args) == 0
    assert sum(seconds for _, seconds in demo.SCENES) == 270
    assert clock.now == 275  # Five-second countdown, then 270-second walkthrough.
    server.close.assert_called_once_with(keep_server=False)


def test_interrupt_still_closes_owned_server(monkeypatch):
    server = SimpleNamespace(
        base_url="http://127.0.0.1:8000", process=None, start=Mock(), close=Mock()
    )
    monkeypatch.setattr(demo, "DemoServer", lambda port: server)
    monkeypatch.setattr(demo.Walkthrough, "scene", Mock(side_effect=KeyboardInterrupt))
    args = SimpleNamespace(port=8000, fast=True, auto_start=False, no_clear=True, keep_server=False)
    with pytest.raises(KeyboardInterrupt):
        demo.run(args)
    server.close.assert_called_once_with(keep_server=False)
