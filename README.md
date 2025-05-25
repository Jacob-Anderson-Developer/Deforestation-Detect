# Deforestation-Detect
This Python script can be run manuall or automatically to detect deforestation

🌳 NDVI Deforestation Detector

A Flask-based web application that helps users detect deforestation by analyzing changes in NDVI (Normalized Difference Vegetation Index) using Google Earth Engine's Sentinel-2 satellite imagery. Users can select a geographic area and receive a downloadable GeoJSON file marking regions of potential deforestation.

📸 Features

📍 Enter bounding box coordinates to define an area of interest (AOI).

🛰️ Fetch Sentinel-2 NDVI imagery before and after a 3-month window.

📉 Calculate NDVI differences to identify areas with significant vegetation loss.

📦 Download deforestation data as a GeoJSON file.

🌐 Preview GeoJSON data instantly on geojson.io.

🧠 Placeholder for Watson integration (future functionality).

💡 How It Works

The user enters minimum and maximum latitude/longitude values via the web form.

The app queries Sentinel-2 SR imagery through Google Earth Engine using the specified bounding box and timeframe.

NDVI values are computed and compared over two periods:

Before: 90 days to 7 days before today

After: Last 7 days

Areas with an NDVI decrease of more than 0.2 are flagged as potential deforestation.

These areas are converted to vector format and returned as a GeoJSON file.

🚀 Getting Started

Prerequisites
Python 3.8+

Google Earth Engine Python API

A GEE service account and credentials .json file

Installation
bash
Copy
Edit
# Clone the repo
git clone https://github.com/yourusername/ndvi-deforestation-detector.git
cd ndvi-deforestation-detector

# Create virtual environment and activate it
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install flask earthengine-api
Set Up Earth Engine Credentials
Update the following values in the code:

python
Copy
Edit
SERVICE_ACCOUNT = 'your-service-account@project-id.iam.gserviceaccount.com'
KEY_PATH = '/full/path/to/your/service-account-key.json'
Run the App
bash
Copy
Edit
python app.py
Then open your browser to http://localhost:5000

📁 Folder Structure
bash
Copy
Edit
ndvi-deforestation-detector/

│

├── app.py                 # Main Flask application

└──README.md               # Project documentation

🧪 API Endpoints
Endpoint	Method	Description
/	GET	HTML form for entering AOI coordinates
/download_geojson	GET	Returns the detected deforestation GeoJSON
/generate_geojson	GET	Returns raw GeoJSON for previewing
/send_to_watson	POST	Placeholder for future Watson integration

🛑 Disclaimer

This project is for educational purposes only and not suitable for real-time deforestation enforcement or precision land use analytics.

📃 License
MIT License
