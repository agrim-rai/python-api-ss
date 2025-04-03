from fastapi import FastAPI
from pydantic import BaseModel
import subprocess

app = FastAPI()

# Define request model
class ScriptRequest(BaseModel):
    script_name: str

@app.post("/execute")
async def execute_code(request: ScriptRequest):
    if request.script_name not in ["paste.py", "copymain.py", "keymain.py"]:
        return {"error": "Invalid script name"}

    try:
        output = subprocess.run(
            ["python3", request.script_name], capture_output=True, text=True, timeout=10
        )
        return {"output": output.stdout, "error": output.stderr}
    except Exception as e:
        return {"error": str(e)}
