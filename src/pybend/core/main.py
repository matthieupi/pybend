"""
PyBend core main — example apps have moved to the workspace root.

The example apps are now standalone:
    cd /workspace/example_api && python main.py
    cd /workspace/example_actor && python main.py
    cd /workspace/example_grants && python main.py
"""
import sys

if __name__ == '__main__':
    print("Example apps have moved to the workspace root.")
    print("Run one of:")
    print("  cd /workspace/example_api && python main.py")
    print("  cd /workspace/example_actor && python main.py")
    print("  cd /workspace/example_grants && python main.py")
    sys.exit(1)
