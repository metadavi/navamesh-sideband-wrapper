# Navamesh Farm App — entry shim.
# Upstream sbapp/main.py preserved verbatim as sbapp/main_upstream.py.
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from farmui.app import run; run()
