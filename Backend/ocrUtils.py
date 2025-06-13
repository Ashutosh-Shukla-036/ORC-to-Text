import platform
from pdf2image import convert_from_path
import pytesseract
import re
from PIL import Image
import cv2
import numpy as np

if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\\Users\\Ashutosh Shukla\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe'
POPPLER_PATH = r'C:\\Users\\Ashutosh Shukla\\scoop\\shims'

def preprocessImage(path):
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Could not read image at {path}")
    
    height, width = img.shape[:2]
    if max(height, width) < 1000:
        img = cv2.resize(img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
    
    processed = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 11
    )
    
    pil_image = Image.fromarray(cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB))
    return pil_image

def extractTextFromImage(imagePath, lang='eng'):
    try:
        processed_img = preprocessImage(imagePath)
        text = pytesseract.image_to_string(processed_img, lang=lang)
        cleaned = cleanExtractedText(text)
        
        if len(cleaned) > 20:  
            return analyzeText(cleaned)
            
    except Exception as e:
        print(f"Preprocessing failed: {e}")
    
    try:
        original_img = Image.open(imagePath)
        text = pytesseract.image_to_string(original_img, lang=lang)
        cleaned = cleanExtractedText(text)
        return analyzeText(cleaned)
    except Exception as e:
        raise RuntimeError(f"Both methods failed: {e}")

def extractTextFromPdf(pdfPath, lang='eng'):
    try:
        pages = convert_from_path(pdfPath)
        combinedText = ""
        for page in pages:
            combinedText += pytesseract.image_to_string(page, lang=lang) + "\n"
        cleaned = cleanExtractedText(combinedText)
        return analyzeText(cleaned)
    except Exception as e:
        raise RuntimeError(f"Error processing PDF: {e}")

def cleanExtractedText(text):
    text = text.replace("-\n", "")
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[ ]{2,}', ' ', text)
    text = re.sub(r' +\n', '\n', text)
    text = re.sub(r'\n +', '\n', text)
    return text.strip()

def analyzeText(text):
    return {
        "cleanText": text,
        "keyValuePairs": extractKeyValuePairs(text),
        "sections": extractSections(text),
        "extractedFields": extractGenericFields(text)
    }

def extractKeyValuePairs(text):
    keyValueMap = {}
    for line in text.split('\n'):
        line = line.strip()

        if not line or len(line.split()) < 2:
            continue

        if re.match(r'^[-•*oOe0]{1,4}\s?[a-zA-Z]', line) and ':' not in line and '-' not in line:
            continue

        match = re.match(r'^([A-Za-z0-9\s\(\)\.\-%]{3,60})\s*[:\-]\s*(.{2,200})$', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()

            if (
                len(key) > 40 or
                not re.search(r'[a-zA-Z]', key) or
                key.lower().startswith(("cofull", "ofull", "odeveloped", "developeda", "oal", "e")) or
                re.match(r'^[oe][A-Z]', key) or
                re.fullmatch(r'[a-zA-Z]?\d{1,4}', key)
            ):
                continue

            camelKey = convertToCamelCase(key)
            keyValueMap[camelKey] = value
    return keyValueMap

def extractSections(text):
    sections = {}
    lines = text.split('\n')
    currentHeading = None
    buffer = []

    for line in lines:
        stripped = line.strip()
        isHeading = len(stripped.split()) <= 5 and (stripped.isupper() or stripped.istitle())

        if isHeading:
            if currentHeading and buffer:
                sections[currentHeading] = buffer
            currentHeading = stripped
            buffer = []
        elif currentHeading:
            buffer.append(stripped)

    if currentHeading and buffer:
        sections[currentHeading] = buffer

    return sections

def extractGenericFields(text):
    fields = {}
    lines = text.split('\n')

    for i, line in enumerate(lines):
        lower = line.lower()

        if "certificate" in lower or "invoice" in lower or "bill" in lower:
            match = re.search(r'[A-Z]{1,4}-?[A-Z0-9]{4,}', line)
            if match:
                fields["documentId"] = match.group()

        if "presented to" in lower or "awarded to" in lower:
            if i + 1 < len(lines):
                possible_name = lines[i + 1].strip()
                if 2 <= len(possible_name.split()) <= 5:
                    fields["recipientName"] = possible_name

        if "date" in lower or "completed" in lower or "issued" in lower:
            date_match = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', line)
            if date_match:
                fields["date"] = date_match.group()

        if "total" in lower or "amount" in lower:
            match = re.search(r'₹?\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?', line)
            if match:
                fields["totalAmount"] = match.group().replace("₹", "").strip()

        if re.search(r'\d{2,3}/\d{2,3}', line) and not re.search(r'\d{1,2}/\d{1,2}/\d{4}', line):
            fields["marks"] = re.search(r'\d{2,3}/\d{2,3}', line).group()

    return fields

def convertToCamelCase(text):
    words = re.sub(r'[^a-zA-Z0-9 ]', '', text).split()
    return words[0].lower() + ''.join(w.capitalize() for w in words[1:]) if words else text
