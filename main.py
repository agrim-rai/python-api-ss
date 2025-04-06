# # from fastapi import FastAPI
# # from pydantic import BaseModel
# # import subprocess

# # app = FastAPI()

# # # Define request model
# # class ScriptRequest(BaseModel):
# #     script_name: str

# # @app.post("/execute")
# # async def execute_code(request: ScriptRequest):
# #     if request.script_name not in ["paste.py", "copymain.py", "keymain.py"]:
# #         return {"error": "Invalid script name"}

# #     try:
# #         output = subprocess.run(
# #             ["python3", request.script_name], capture_output=True, text=True, timeout=10
# #         )
# #         return {"output": output.stdout, "error": output.stderr}
# #     except Exception as e:
# #         return {"error": str(e)}



# from fastapi import FastAPI
# from pydantic import BaseModel
# import subprocess
# import json

# app = FastAPI()

# class ScriptRequest(BaseModel):
#     script_name: str
#     object_id: str  # New field to pass object_id

# @app.post("/execute")
# async def execute_code(request: ScriptRequest):
#     if request.script_name not in ["paste.py", "copymain.py", "keymain.py","cpp.py","py.py","java.py","javascript.py","tab.py"]:
#         return {"error": "Invalid script name"}

#     try:
#         # Pass object_id as an argument to the script
#         output = subprocess.run(
#             ["python3", request.script_name, request.object_id], 
#             capture_output=True, 
#             text=True, 
#             timeout=10
#         )

#         stdout = output.stdout.strip()
#         stderr = output.stderr.strip()

#         if stderr:
#             return {"error": stderr}

#         # Convert output to JSON if possible
#         try:
#             return json.loads(stdout)
#         except json.JSONDecodeError:
#             return {"error": "Invalid JSON format in script output", "raw_output": stdout}

#     except Exception as e:
#         return {"error": str(e)}




from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import json
import logging

# Configure logging for the FastAPI app
logging.basicConfig(level=logging.INFO)

app = FastAPI()

class ScriptRequest(BaseModel):
    script_name: str
    object_id: str  # Field to pass object_id

@app.post("/execute")
async def execute_code(request: ScriptRequest):
    if request.script_name not in ["paste.py", "copymain.py", "keymain.py", "cpp.py", "py.py", "java.py", "javascript.py", "tab.py"]:
        return {"error": "Invalid script name"}

    try:
        # Pass object_id as an argument to the script
        output = subprocess.run(
            ["python3", request.script_name, request.object_id], 
            capture_output=True, 
            text=True, 
            timeout=30  # Increased timeout for potentially slow database operations
        )

        # Check return code first
        if output.returncode != 0:
            return {"error": f"Script exited with code {output.returncode}", "stderr": output.stderr}

        stdout = output.stdout.strip()
        stderr = output.stderr.strip()

        # Log the raw output for debugging
        logging.info(f"Raw stdout: {stdout[:200]}...")  # Truncate for logging
        if stderr:
            logging.warning(f"Script stderr: {stderr}")

        # Try to parse the stdout as JSON
        try:
            result = json.loads(stdout)
            return result
        except json.JSONDecodeError as e:
            return {
                "error": f"Invalid JSON in script output: {str(e)}",
                "stdout": stdout,
                "stderr": stderr
            }

    except subprocess.TimeoutExpired:
        return {"error": "Script execution timed out"}
    except Exception as e:
        return {"error": f"Execution error: {str(e)}"}