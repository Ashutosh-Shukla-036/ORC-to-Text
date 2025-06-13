from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from ocrUtils import extractTextFromImage, extractTextFromPdf

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload', methods=['POST'])
def handleFileUpload():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    uploadedFile = request.files['file']
    fileName = uploadedFile.filename
    filePath = os.path.join(UPLOAD_FOLDER, fileName)
    uploadedFile.save(filePath)

    try:
        if fileName.lower().endswith(('.jpg', '.jpeg', '.png')):
            result = extractTextFromImage(filePath)
        elif fileName.lower().endswith('.pdf'):
            result = extractTextFromPdf(filePath)
        else:
            return jsonify({"error": "Unsupported file type"}), 400

        return jsonify(result), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
