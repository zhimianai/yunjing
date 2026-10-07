import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['CUDA_VISIBLE_DEVICES'] = ''

from ai智能问答 import create_app
app = create_app()
