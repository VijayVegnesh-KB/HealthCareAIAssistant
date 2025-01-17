import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import autogen
from autogen import AssistantAgent, UserProxyAgent
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent
from autogen.retrieve_utils import TEXT_FORMATS
import xml.etree.ElementTree as ET  # Import for parsing XML
import json
import chromadb
from pymongo import MongoClient
from datetime import datetime

# Check if the XML file is accessible
if os.path.exists("../ProductCatelog.xml"):
    print("XML file is accessible.")
else:
    print("XML file not found.")

app = Flask(__name__)

# CORS configuration to allow requests from Flutter app
CORS(app)

# Load configuration for the assistant
config_list = autogen.config_list_from_json(env_or_file="OAI_CONFIG_LIST.json")

# Initialize AssistantAgent to handle general queries and greetings
healthassistant = AssistantAgent(
    name="healthassistant",
    system_message="You are a healthcare assistant. First provide a calming message for non-urgent symptoms "
                   "For medical symptoms, suggest medicines or medical kits(if applicable) with prices and images. All responses should be in JSON format. "
                   "Remind the user to consult a doctor for confirmation. Handle general queries normally"
                   "In the JSON, the calming message should be under the key 'message', medications as 'medicines' and reminder message as 'disclaimer'",
    llm_config={
        "timeout": 600,
        "cache_seed": 42,
        "config_list": config_list,
    },
)

classifier = AssistantAgent(
    name="classifier",
    system_message="You are a classifier. The output would be in JSON format",
    llm_config={
        "timeout": 600,
        "cache_seed": 42,
        "config_list": config_list,
    },
)

# Department classifier for medical queries
department_classifier = AssistantAgent(
    name="department_classifier",
    system_message="Classify the medical query into one of the following departments: 'Cardiology', 'Neurology', 'Dermatology', 'Orthopedics', 'General'. "
                   "Respond with JSON in the form {'department': 'Cardiology'}",
    llm_config={
        "timeout": 600,
        "cache_seed": 42,
        "config_list": config_list,
    },
)


corpus_file = "../ProductCatelog.xml"

ragproxyagent = RetrieveUserProxyAgent(
    name="RetrieveMedicineProxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    retrieve_config={
        "task": "code",
        "docs_path": corpus_file,
        "chunk_token_size": 2000,
        "model": config_list[0]["model"],
        "client": chromadb.PersistentClient(path="/tmp/chromadb"),
        "get_or_create": True,
        "embedding_model": "all-MiniLM-L6-v2",
    },
    code_execution_config=False,
)


# Initialize UserProxyAgent
user_proxy = UserProxyAgent(
    name="UserProxy",
    human_input_mode="NEVER",
    system_message="Please say that the context is not relevant to medicine.",
    code_execution_config={
        "last_n_messages": 1,
        "work_dir": "tasks",
        "use_docker": False,
    },
)


# Define request structure and validation for Flask
def classify_intent(user_input):
    classification_prompt = (
        f"Classify the following input as either 'medical', 'greeting', or 'general':\n\n"
        f"Input: {user_input}\n"
        "Please provide the classification in one word."
    )

    classification_response = healthassistant.initiate_chat(
        classifier, message=classification_prompt, max_turns=1, summary_method="last_msg"
    )
    #print(f"classification_response: {classification_response}")

    summary = classification_response.summary
    #print(f"summary: {summary}")

    clean_response = summary.strip().strip("```json").strip("```")
    
    try:
        response_json = json.loads(clean_response)
        classification = response_json.get("classification", "").lower()
        print(f"classification: {classification}")
    except json.JSONDecodeError:
        classification = "general"
    
    return classification


# Classify medical queries into departments
def classify_department(user_input):
    department_prompt = (
        f"Classify the following medical query into a department:\n\n"
        f"Input: {user_input}\n"
        "Please provide the department classification in the format {'department': 'Cardiology'}."
    )

    department_response = healthassistant.initiate_chat(
        department_classifier, message=department_prompt, max_turns=1, summary_method="last_msg"
    )
    
    summary = department_response.summary
    clean_response = summary.strip().strip("```json").strip("```")
    
    try:
        response_json = json.loads(clean_response)
        classification = response_json.get("department", "").lower()
    except json.JSONDecodeError:
        department = "General"
    
    return department


def handle_user_query(user_input):
    print("XYZ ")
    print(f"user_input: {user_input}")
    intent = classify_intent(user_input)
    print(f"intent: {intent}")

    if intent == "greeting":
        return {"message": "Hello! How can I assist you today with your health concerns?"}

    if intent == "medical":
        department = classify_department(user_input)
        print(f"Classified department: {department}")
    
        chat_result = ragproxyagent.initiate_chat(
            healthassistant, message=ragproxyagent.message_generator, problem=user_input, n_results=5
        )
        return chat_result
    
    return {"message": "I may not have an answer to that, but I'd love to help with health-related questions, product recommendations, or wellness advice. Let me know how I can assist!"}


@app.route("/recommendation/", methods=["POST"])
def get_recommendation():
    try:
        data = request.get_json()
        input_message = data.get("message")
        
        if not input_message:
            return jsonify({"error": "No message provided"}), 400
        
        print(f"Received message: {input_message}")
        medicine_info = handle_user_query(input_message)
        print(f"Medicine information retrieved: {medicine_info}")
        
        if not medicine_info:
            return jsonify({"error": "No medicine information found."}), 404
        
        return jsonify({"response": medicine_info})

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
    

# Connect to MongoDB
mongo_client = MongoClient("mongodb://localhost:27017/")  # Replace with your MongoDB URI
db = mongo_client["HealthcareAssistant"]  # Database name
orders_collection = db["orders"]  # Collection name

@app.route("/submit_order/", methods=["POST"])
def submit_order():
    try:
        data = request.get_json()

        # Ensure all required fields are present
        required_fields = ["name", "address", "creditCardNumber", "medicine"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        # Prepare order document
        order_document = {
            "name": data["name"],
            "address": data["address"],
            "creditCardNumber": data["creditCardNumber"][-4:],  # Store only last 4 digits for security
            "medicine": data["medicine"],  # Includes name, price, and image details
            "orderNumber": datetime.now().strftime("%Y%m%d%H%M%S"),  # Generate a timestamp-based order number
            "timestamp": datetime.now(),  # Add a timestamp
        }

        # Insert order into MongoDB
        orders_collection.insert_one(order_document)

        return jsonify({"message": "Order submitted successfully", "orderNumber": order_document["orderNumber"]}), 201

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": "Internal Server Error"}), 500


# To run this backend, use the following command:
# python app.py
if __name__ == "__main__":
    app.run(debug=True)
