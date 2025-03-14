from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import requests
from datetime import datetime
from bson import ObjectId

# Load environment variables
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Initialize Flask app
app = Flask(__name__)

# Allow CORS for frontend access
CORS(app, resources={
    r"/*": {"origins": ["http://localhost:3000", "https://clg-navigator.vercel.app"]}}, supports_credentials=True)

# Connect to MongoDB
try:
    client = MongoClient(MONGO_URL)
    db = client["cmr_navigator"]
    user_collection = db["user_data"]
    clg_collection = db["clg_data"]
    # ✅ Collection for storing event details
    event_collection = db["Event_data"]
except Exception as e:
    print("MongoDB Connection Error:", e)
    exit(1)

# 📌 Google Login Route
@app.route("/users/google-login", methods=["POST"])
def google_login():
    try:
        data = request.json
        token = data.get("credential")

        if not token:
            return jsonify({"success": False, "error": "Missing Google token"}), 400

        # Verify Google Token
        google_response = requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
        if google_response.status_code != 200:
            return jsonify({"success": False, "error": "Invalid Google Token"}), 401

        user_info = google_response.json()

        user_data = {
            "google_id": user_info.get("sub"),
            "name": user_info.get("name"),
            "email": user_info.get("email"),
            "profile_picture": user_info.get("picture"),
            "role": "student",
            "last_login": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }

        # Check if user exists
        existing_user = user_collection.find_one({"email": user_data["email"]})

        if existing_user:
            user_collection.update_one({"email": user_data["email"]}, {
                                       "$set": {"last_login": user_data["last_login"]}})
            existing_user["_id"] = str(existing_user["_id"])
            return jsonify({"success": True, "message": "User logged in", "data": existing_user}), 200

        # Register new user
        inserted_user = user_collection.insert_one(user_data)
        user_data["_id"] = str(inserted_user.inserted_id)

        return jsonify({"success": True, "message": "New user registered", "data": user_data}), 201

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 📌 Fetch user details by email


@app.route("/users/<string:email>", methods=["GET"])
def get_user(email):
    try:
        user = user_collection.find_one({"email": email})
        if user:
            user["_id"] = str(user["_id"])
            return jsonify({"success": True, "data": user}), 200
        return jsonify({"success": False, "message": "User not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 📌 GET route to fetch all colleges
@app.route("/colleges", methods=["GET"])
def get_colleges():
    try:
        colleges = list(clg_collection.find({}))
        for college in colleges:
            college["_id"] = str(college["_id"])
        return jsonify({"success": True, "data": colleges}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/colleges", methods=["POST"])
def add_college():
    try:
        data = request.get_json()

        required_fields = ["name", "location", "website", "contact",
                           "facilities", "departments", "courses", "city", "state", "branches"]

        if not data:
            return jsonify({"success": False, "error": "Request must contain JSON data"}), 400

        missing_fields = [
            field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({"success": False, "error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

        # Validate location fields
        if not isinstance(data.get("location"), dict) or not all(key in data["location"] for key in ["latitude", "longitude", "address"]):
            return jsonify({"success": False, "error": "Invalid location data. Must include latitude, longitude, and address."}), 400

        # Validate contact fields
        if not isinstance(data.get("contact"), dict) or not all(key in data["contact"] for key in ["email", "phone"]):
            return jsonify({"success": False, "error": "Invalid contact data. Must include email and phone."}), 400

        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()

        inserted_college = clg_collection.insert_one(data)
        data["_id"] = str(inserted_college.inserted_id)

        return jsonify({"success": True, "message": "College added successfully", "data": data}), 201

    except Exception as e:
        app.logger.error(f"Error adding college: {str(e)}")
        return jsonify({"success": False, "error": "Internal Server Error. Please try again later."}), 500
# 📌 DELETE route to remove a college by name


@app.route("/colleges/<string:name>", methods=["DELETE"])
def delete_college(name):
    try:
        result = clg_collection.delete_one({"name": name})
        if result.deleted_count > 0:
            return jsonify({"success": True, "message": "College deleted successfully"}), 200
        return jsonify({"success": False, "message": "College not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 📌 UPDATE route to modify college data by name


@app.route("/colleges/<string:name>", methods=["PUT"])
def update_college(name):
    try:
        updated_data = request.json
        result = clg_collection.update_one(
            {"name": name}, {"$set": updated_data})
        if result.modified_count > 0:
            return jsonify({"success": True, "message": "College updated successfully"}), 200
        return jsonify({"success": False, "message": "No changes made or college not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 📌 POST route to add a new event


@app.route("/events", methods=["POST"])
def add_event():
    try:
        data = request.json

        required_fields = ["college_name", "event_name",
                           "description", "date", "location"]
        if not all(field in data for field in required_fields):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        # ✅ Ensure date is converted to a Python datetime object
        try:
            data["date"] = datetime.strptime(data["date"], "%Y-%m-%d")
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format"}), 400

        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()

        inserted_event = event_collection.insert_one(data)
        data["_id"] = str(inserted_event.inserted_id)

        return jsonify({"success": True, "message": "Event added successfully", "data": data}), 201

    except Exception as e:
        print("❌ Server Error:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

# 📌 GET route to fetch all events


@app.route("/events", methods=["GET"])
def get_events():
    try:
        events = list(event_collection.find({}))
        for event in events:
            event["_id"] = str(event["_id"])
            if "date" in event and isinstance(event["date"], datetime):
                event["date"] = event["date"].isoformat()
            if "created_at" in event and isinstance(event["created_at"], datetime):
                event["created_at"] = event["created_at"].isoformat()
            if "updated_at" in event and isinstance(event["updated_at"], datetime):
                event["updated_at"] = event["updated_at"].isoformat()

        return jsonify({"success": True, "data": events}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 📌 PUT route to update an event by ID
@app.route("/events/<string:event_id>", methods=["PUT"])
def update_event(event_id):
    try:
        updated_data = request.json
        if "date" in updated_data:
            updated_data["date"] = datetime.strptime(
                updated_data["date"], "%Y-%m-%dT%H:%M:%SZ")

        updated_data["updated_at"] = datetime.utcnow()

        result = event_collection.update_one(
            {"_id": ObjectId(event_id)}, {"$set": updated_data})
        if result.modified_count > 0:
            return jsonify({"success": True, "message": "Event updated successfully"}), 200
        return jsonify({"success": False, "message": "No changes made or event not found"}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 📌 DELETE route to remove an event by ID


@app.route("/events/<string:event_id>", methods=["DELETE"])
def delete_event(event_id):
    try:
        result = event_collection.delete_one({"_id": ObjectId(event_id)})
        if result.deleted_count > 0:
            return jsonify({"success": True, "message": "Event deleted successfully"}), 200
        return jsonify({"success": False, "message": "Event not found"}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/map-data", methods=["GET"])
def get_map_data():
    try:
        facilities = list(db["clg_facility_data"].find({}))
        for facility in facilities:
            facility["_id"] = str(facility["_id"])

        return jsonify({"success": True, "data": facilities}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/colleges/<string:college_name>/rate", methods=["POST"])
def rate_college(college_name):
    try:
        data = request.json
        required_fields = ["user_email", "rating", "message"]

        # Validate request data
        if not all(field in data for field in required_fields):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        # Check if user exists
        user = user_collection.find_one({"email": data["user_email"]})
        if not user:
            return jsonify({"success": False, "error": "Invalid user"}), 403

        # Check if college exists
        college = clg_collection.find_one({"name": college_name})
        if not college:
            return jsonify({"success": False, "error": "College not found"}), 404

        # Create review object
        review = {
            "user_id": str(user["_id"]),
            "user_email": data["user_email"],
            "rating": data["rating"],
            "message": data["message"],
            "timestamp": datetime.utcnow()
        }

        # Add review to the college document
        clg_collection.update_one(
            {"name": college_name},
            {"$push": {"reviews": review}}
        )

        return jsonify({"success": True, "message": "Review added successfully"}), 201

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Run the Flask application (Production Mode)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
