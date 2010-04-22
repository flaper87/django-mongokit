#!/bin/bash
coverage run tests.py
coverage report __init__.py document.py mongodbkit/__init__.py shortcut.py mongodbkit/base.py
coverage html __init__.py document.py mongodbkit/__init__.py shortcut.py mongodbkit/base.py
ls htmlcov/index.html