import os
import subprocess
import sys

try:
    # Standard Python script execution
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # CML runs Scripts in a notebook/interactive context where __file__ is not defined.
    # The project root is the working directory; navigate to the demo subdirectory.
    script_dir = os.path.join(os.getcwd(), "demos", "cloudera-ai-id-rag-demo")

os.chdir(script_dir)
sys.exit(subprocess.call(["bash", "deployment/launch_app.sh"]))
