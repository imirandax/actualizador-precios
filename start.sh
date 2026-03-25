#!/bin/bash
playwright install chromium
playwright install-deps chromium
python server.py
