from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import json
from checkcodetype import detect_language
from checkcodetype import fetch_document_by_id
from pymongo import MongoClient
from bson.objectid import ObjectId

app = FastAPI()

# MongoDB connection
def get_mongodb_connection():
    client = MongoClient("mongodb+srv://admin:7vNJvFHGPVvbWBRD@syntaxsentry.rddho.mongodb.net/?retryWrites=true&w=majority&appName=syntaxsentry")
    db = client["test"]
    return db

# Function to store AI responses in MongoDB
def store_ai_response(document_id, event_type, response_data, status="success"):
    try:
        db = get_mongodb_connection()
        airesponse_collection = db["airesponse"]
        
        # Prepare the document to insert
        response_doc = {
            "documentId": document_id,
            "eventType": event_type,
            "response": response_data,
            "status": status
        }
        
        # Insert the document
        result = airesponse_collection.insert_one(response_doc)
        return result.inserted_id
    except Exception as e:
        print(f"Error storing AI response: {str(e)}")
        return None

class ScriptRequest(BaseModel):
    script_name: str
    object_id: str  # New field to pass object_id

@app.post("/execute")
async def execute_code(request: ScriptRequest):
    if request.script_name not in ["paste.py", "copymain.py", "keymain.py","cpp.py","py.py","java.py","javascript.py","tab.py"]:
        return {"error": "Invalid script name"}

    try:
        # Determine event type based on script name
        event_type = "copy" if request.script_name == "copymain.py" else "paste" if request.script_name == "paste.py" else "key" if request.script_name == "keymain.py" else "tab" if request.script_name == "tab.py" else "code"
        
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
            # Store error response in MongoDB
            error_response = {"error": stderr}
            store_ai_response(
                document_id=request.object_id,
                event_type=event_type,
                response_data={
                    "script_name": request.script_name,
                    "object_id": request.object_id,
                    "error": stderr
                },
                status="error"
            )
            return error_response

        # Convert output to JSON if possible
        try:
            response_data = json.loads(stdout)
            
            # Store successful response in MongoDB
            store_ai_response(
                document_id=request.object_id,
                event_type=event_type,
                response_data={
                    "script_name": request.script_name,
                    "object_id": request.object_id,
                    **response_data
                }
            )
            
            return response_data
        except json.JSONDecodeError:
            # Store error response in MongoDB
            error_response = {"error": "Invalid JSON format in script output", "raw_output": stdout}
            store_ai_response(
                document_id=request.object_id,
                event_type=event_type,
                response_data={
                    "script_name": request.script_name,
                    "object_id": request.object_id,
                    "error": "Invalid JSON format in script output",
                    "raw_output": stdout
                },
                status="error"
            )
            return error_response

    except Exception as e:
        # Store error response in MongoDB
        error_response = {"error": str(e)}
        store_ai_response(
            document_id=request.object_id,
            event_type=event_type,
            response_data={
                "script_name": request.script_name,
                "object_id": request.object_id,
                "error": str(e)
            },
            status="error"
        )
        return error_response
