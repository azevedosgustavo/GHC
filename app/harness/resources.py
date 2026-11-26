"""Paths to application resources in source and packaged builds."""
import os
import sys


def asset_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", name)
