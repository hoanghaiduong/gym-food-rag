import sys
import os

sys.path.append(os.getcwd())

def trace_imports(frame, event, arg):
    if event != 'call':
        return
    co = frame.f_code
    func_name = co.co_name
    if func_name == '<module>':
        filename = co.co_filename
        if 'gym-food-rag' in filename:
            print(f"Importing: {filename}")
    return

sys.settrace(trace_imports)

print("Starting import of app.main...")
try:
    from app.main import app
    print("Successfully imported app.main")
except Exception as e:
    print(f"Error importing app.main: {e}")
