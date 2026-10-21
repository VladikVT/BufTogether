"""
BufTogether - macOS Client Entrypoint.
Runs the macOS Client daemon from the buftogether package.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buftogether.client import main

if __name__ == '__main__':
    main()
