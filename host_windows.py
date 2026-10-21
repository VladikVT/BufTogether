"""
BufTogether - Windows Host Entrypoint.
Runs the Windows Host daemon from the buftogether package.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buftogether.host import main

if __name__ == '__main__':
    main()
