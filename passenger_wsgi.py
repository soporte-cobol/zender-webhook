import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

try:
    from app import app as application
except Exception as e:
    import traceback
    with open(os.path.join(os.path.dirname(__file__), 'startup_error.txt'), 'w') as f:
        traceback.print_exc(file=f)
    raise
