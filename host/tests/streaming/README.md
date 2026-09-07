# Streaming tests

Tests for the host streaming layer.

They cover stream defaults and validation, encoder profile validation, runtime state transitions, frame telemetry, and adaptive quality behavior.

Run this group from the repository root with:

```text
python -m unittest discover -s host/tests/streaming -p "test_*.py"
```

The tests are intentionally independent of a physical ESP32. The current capture implementation reports the Windows capture backend state; it does not yet acquire real frames.
