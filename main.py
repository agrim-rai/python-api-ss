# from fastapi import FastAPI
# from pydantic import BaseModel
# import subprocess

# app = FastAPI()

# # Define request model
# class ScriptRequest(BaseModel):
#     script_name: str

# @app.post("/execute")
# async def execute_code(request: ScriptRequest):
#     if request.script_name not in ["paste.py", "copymain.py", "keymain.py"]:
#         return {"error": "Invalid script name"}

#     try:
#         output = subprocess.run(
#             ["python3", request.script_name], capture_output=True, text=True, timeout=10
#         )
#         return {"output": output.stdout, "error": output.stderr}
#     except Exception as e:
#         return {"error": str(e)}



from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import json

app = FastAPI()

class ScriptRequest(BaseModel):
    script_name: str
    object_id: str  # New field to pass object_id

@app.post("/execute")
async def execute_code(request: ScriptRequest):
    if request.script_name not in ["paste.py", "copymain.py", "keymain.py","cpp.py"]:
        return {"error": "Invalid script name"}

    try:
        # Pass object_id as an argument to the script
        output = subprocess.run(
            ["python3", request.script_name, request.object_id], 
            capture_output=True, 
            text=True, 
            timeout=10
        )

        stdout = output.stdout.strip()
        stderr = output.stderr.strip()

        if stderr:
            return {"error": stderr}

        # Convert output to JSON if possible
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON format in script output", "raw_output": stdout}

    except Exception as e:
        return {"error": str(e)}
