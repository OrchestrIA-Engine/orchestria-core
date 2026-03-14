import sys, os, runpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py'), run_name='__main__')
