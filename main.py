import os
import sys
import asyncio

_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(_ROOT)
sys.path.insert(0, _ROOT)

from bot import main

if __name__ == "__main__":
    asyncio.run(main())