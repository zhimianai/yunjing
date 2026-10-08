import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

from app_factory import create_app
app = create_app()