import os
import subprocess

try:
    # Standard Python script execution
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # CML runs Scripts in IPython/notebook context where __file__ is not defined.
    # The project root is the working directory; navigate to the demo subdirectory.
    script_dir = os.path.join(os.getcwd(), "demos", "cloudera-ai-id-rag-demo")

os.chdir(script_dir)

# os.execvp() kills the IPython kernel in CML context — do not use it.
# Use subprocess.call() + os._exit(): sys.exit() raises SystemExit which
# IPython catches and treats as an error; os._exit() bypasses that.
exit_code = subprocess.call(["bash", "deployment/launch_app.sh"])
os._exit(exit_code)
