import json
import os
import tempfile
import unittest

from harness import tools
from harness.client import parse_stream


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "a.txt"), "w") as f:
            f.write("um\ndois\ntres\n")

    def test_read_range(self):
        r = tools.execute(self.d, "read_file", json.dumps({"path": "a.txt", "start_line": 2, "end_line": 3}))
        self.assertEqual(r, "2: dois\n3: tres")

    def test_escape_blocked(self):
        r = tools.execute(self.d, "read_file", json.dumps({"path": "../x"}))
        self.assertIn("fora do workspace", r)

    def test_list(self):
        self.assertEqual(tools.execute(self.d, "list_dir", "{}"), "a.txt")


class StreamTest(unittest.TestCase):
    def test_tool_call_assembly(self):
        ev = [
            {"choices": [{"delta": {"content": "oi"}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "read_file", "arguments": "{\"pa"}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "th\":\"a\"}"}}]}}]},
        ]
        lines = ["data: " + json.dumps(e) for e in ev] + ["data: [DONE]"]
        m = parse_stream(lines)
        self.assertEqual(m["content"], "oi")
        self.assertEqual(m["tool_calls"][0]["function"]["arguments"], '{"path":"a"}')


if __name__ == "__main__":
    unittest.main()
