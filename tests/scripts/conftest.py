import sys
from pathlib import Path

# Cho test nhập được `scripts.dr` khi chạy pytest từ bất kỳ thư mục nào.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
