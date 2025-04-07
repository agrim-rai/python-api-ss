from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import json
from checkcodetype import detect_language
from checkcodetype import fetch_document_by_id

app = FastAPI()

class ScriptRequest(BaseModel):
    script_name: str
    object_id: str  # New field to pass object_id

@app.post("/execute")
async def execute_code(request: ScriptRequest):
    if request.script_name not in ["paste.py", "copymain.py", "keymain.py","cpp.py","py.py","java.py","javascript.py","tab.py"]:
        return {"error": "Invalid script name"}

    try:
        # Pass object_id as an argument to the script
        if(request.script_name in ["paste.py", "copymain.py", "keymain.py","tab.py"]):
            output = subprocess.run(
                ["python3", request.script_name, request.object_id], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
        else:
            if(detect_language(fetch_document_by_id(request.object_id)['code']) == 'Java'):
                output = subprocess.run(
                    ["python3", 'java.py', request.object_id], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
            elif(detect_language(fetch_document_by_id(request.object_id)['code']) == 'Python'):
                output = subprocess.run(
                    ["python3", 'py.py', request.object_id], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
            elif(detect_language(fetch_document_by_id(request.object_id)['code']) == 'C++'):
                output = subprocess.run(
                    ["python3", 'cpp.py', request.object_id], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
            elif(detect_language(fetch_document_by_id(request.object_id)['code']) == 'Javascript'):
                output = subprocess.run(
                    ["python3", 'javascript.py', request.object_id], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
            else:
                output.stdout = "could not find language amaong cpp,java,js,py"
                output.stderr = "500"


        
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
