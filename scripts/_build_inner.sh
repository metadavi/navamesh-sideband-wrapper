#!/bin/bash
# _build_inner.sh — Runs inside the kivy/buildozer container.
set -e

exec buildozer android debug
