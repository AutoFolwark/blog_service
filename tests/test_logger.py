import logging

from core.logger import InterceptHandler, logger


def test_stdlib_record_is_written_by_loguru():
    record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="server ready",
        args=(),
        exc_info=None,
    )
    messages: list[str] = []
    sink_id = logger.add(
        lambda message: messages.append(message), format="{level} {message}"
    )
    try:
        InterceptHandler().emit(record)
    finally:
        logger.remove(sink_id)
    assert any("INFO" in message and "server ready" in message for message in messages)
