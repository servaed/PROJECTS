import os

try:
    # Standard Python script execution
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # CML runs Scripts in IPython/notebook context where __file__ is not defined.
    # The project root is the working directory; navigate to the demo subdirectory.
    script_dir = os.path.join(os.getcwd(), "demos", "cloudera-ai-id-rag-demo")

os.chdir(script_dir)

# Replace this Python process entirely with bash → launch_app.sh → exec uvicorn.
# This creates a clean single-process chain: CML kills one PID and uvicorn exits.
# subprocess.call() leaves Python alive as a parent, causing orphan uvicorn on restart.
os.execvp("bash", ["bash", "deployment/launch_app.sh"])
