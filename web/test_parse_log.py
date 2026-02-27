#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal unit test for parse_log_for_progress."""

from api import parse_log_for_progress

def test_parse_log_no_progress_lines():
    content = "[2026-02-23 00:00:00] 任务启动\n"
    result = parse_log_for_progress(content)
    assert result["progress"] == 0
    assert result["total"] == 0
    assert result["downloaded"] == 0
    assert result["current_company"] == ""

if __name__ == "__main__":
    test_parse_log_no_progress_lines()
    print("ok")
