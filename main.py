from fastapi import FastAPI
import subprocess

app = FastAPI()

@app.post("/execute")
async def execute_code(script_name: str):
    if script_name not in ["paste.py", "copymain.py", "keymain.py"]:
        return {"error": "Invalid script name"}

    try:
        output = subprocess.run(
            ["python3", script_name], capture_output=True, text=True, timeout=10
        )
        return {"output": output.stdout, "error": output.stderr}
    except Exception as e:
        return {"error": str(e)}
