from flask import Flask, request, render_template_string, send_file, jsonify
import ee
import json
from datetime import datetime, timedelta, timezone
import io
import smtplib
from email.message import EmailMessage
import os
import requests
import logging
import mimetypes
from email.utils import make_msgid

# Setup logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = Flask(__name__)

# HTML Interface
@app.route('/')
def home():
    return render_template_string("""<!DOCTYPE html>
    <html>
    <head><title>NDVI Deforestation Detector</title></head>
                                          <style>
            /* Reset and base */
            * {
                box-sizing: border-box;
            }
            body {
                background: #1e1e2f; /* dark blue-purple */
                color: #e0e0f0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 0;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
            }
            h1 {
                font-weight: 700;
                margin-bottom: 0.1em;
                color: #70a1ff;
                text-shadow: 0 0 8px #5f7cffaa;
            }
            p {
                color: #a0a0bf;
                margin-top: 0;
                margin-bottom: 2em;
                font-size: 1.1em;
            }
            form {
                background: #2a2a40;
                padding: 2em 3em;
                border-radius: 12px;
                box-shadow: 0 8px 20px rgba(0,0,0,0.4);
                width: 350px;
                text-align: center;
            }
            table {
                width: 100%;
                border-spacing: 12px 14px;
            }
            td {
                vertical-align: middle;
                text-align: left;
                color: #d0d0ff;
                font-weight: 600;
                font-size: 1rem;
                user-select: none;
                padding-left: 8px;
            }
            input[type="text"] {
                width: 100%;
                padding: 10px 12px;
                border: none;
                border-radius: 8px;
                font-size: 1rem;
                font-weight: 500;
                color: #333;
                outline-offset: 3px;
                outline-color: #70a1ff;
                transition: outline-color 0.3s ease;
            }
            input[type="text"]:focus {
                outline-color: #4099ff;
                box-shadow: 0 0 6px #4099ff66;
            }
            button {
                width: 100%;
                padding: 14px 0;
                margin: 12px 0 0 0;
                border: none;
                border-radius: 10px;
                font-weight: 700;
                font-size: 1.15rem;
                color: #fff;
                background: linear-gradient(90deg, #0077ff, #00c3ff);
                box-shadow: 0 4px 10px #0077ffcc;
                cursor: pointer;
                transition: background 0.3s ease, box-shadow 0.3s ease;
            }
            button:hover, button:focus {
                background: linear-gradient(90deg, #00c3ff, #0077ff);
                box-shadow: 0 6px 14px #00c3ffcc;
                outline: none;
            }
            button:active {
                transform: translateY(1px);
                box-shadow: 0 3px 6px #0066cccc;
            }
        </style>
    <body>
        <h1>Detect Deforestation with NDVI</h1>
        <form id="coordsForm">
            <label>Min Longitude: <input type="text" name="min_lon" value="-111.361"></label><br>
            <label>Min Latitude: <input type="text" name="min_lat" value="57.36"></label><br>
            <label>Max Longitude: <input type="text" name="max_lon" value="-111.36"></label><br>
            <label>Max Latitude: <input type="text" name="max_lat" value="57.44"></label><br>
            <button type="button" onclick="downloadGeoJSON()">Download GeoJSON</button>
            <button type="button" onclick="previewGeoJSON()">Preview on geojson.io</button>
            <button type="button" onclick="sendToWatson()">Run Watson Analysis</button>
        </form>
        <script>
            function getFormParams() {
                const form = document.getElementById('coordsForm');
                const params = new URLSearchParams(new FormData(form));
                return params.toString();
            }
            function downloadGeoJSON() {
                window.location.href = '/download_geojson?' + getFormParams();
            }
            async function previewGeoJSON() {
                const response = await fetch('/generate_geojson?' + getFormParams());
                const geojson = await response.json();
                const encoded = encodeURIComponent(JSON.stringify(geojson));
                window.open(`https://geojson.io/#data=data:application/json,${encoded}`);
            }
            async function sendToWatson() {
              try {
                const response = await fetch('/send_to_watson', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(Object.fromEntries(new FormData(document.getElementById('coordsForm'))))
                });

            if (!response.ok) {
               alert('Error: ' + response.statusText);
               return;
            }

        const responseData = await response.json();

        // Show success alert
        alert('Watson analysis complete. Authorities have been notified.');
                                  
    } catch (error) {
        alert('Fetch error: ' + error.message);
    }
}

        </script>
    </body>
    </html>""")

# Deforestation detection
def get_deforestation_geojson(min_lon, min_lat, max_lon, max_lat):
    SERVICE_ACCOUNT = 'Placeholder'
    KEY_PATH = 'Placeholder'
    credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_PATH)
    ee.Initialize(credentials)

    aoi = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
    today = datetime.now(timezone.utc)
    three_months_ago = today - timedelta(days=90)
    seven_days_ago = today - timedelta(days=7)

    def maskS2sr(image):
        scl = image.select('SCL')
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
        return image.updateMask(mask).divide(10000)

    def addNDVI(image):
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return image.addBands(ndvi)

    before = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
              .filterDate(three_months_ago, seven_days_ago)
              .filterBounds(aoi)
              .map(maskS2sr).map(addNDVI).median().select('NDVI'))

    after = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
             .filterDate(seven_days_ago, today)
             .filterBounds(aoi)
             .map(maskS2sr).map(addNDVI).median().select('NDVI'))

    diff = before.subtract(after).rename('NDVI_change')
    deforestation = diff.gt(0.2)

    vectors = deforestation.selfMask().reduceToVectors(
        geometry=aoi,
        scale=10,
        geometryType='polygon',
        labelProperty='deforestation',
        maxPixels=1e10
    )
    return vectors.getInfo()

@app.route('/generate_geojson')
def generate_geojson():
    min_lon = float(request.args.get('min_lon'))
    min_lat = float(request.args.get('min_lat'))
    max_lon = float(request.args.get('max_lon'))
    max_lat = float(request.args.get('max_lat'))
    geojson = get_deforestation_geojson(min_lon, min_lat, max_lon, max_lat)
    return jsonify(geojson)

@app.route('/download_geojson')
def download_geojson():
    min_lon = float(request.args.get('min_lon'))
    min_lat = float(request.args.get('min_lat'))
    max_lon = float(request.args.get('max_lon'))
    max_lat = float(request.args.get('max_lat'))
    geojson = get_deforestation_geojson(min_lon, min_lat, max_lon, max_lat)
    geojson_bytes = json.dumps(geojson).encode('utf-8')
    return send_file(io.BytesIO(geojson_bytes), download_name='deforestation.geojson', as_attachment=True, mimetype='application/json')

@app.route('/send_to_watson', methods=['POST'])
def send_to_watson():
    try:
        data = request.get_json()
        logging.info(f"Received data for Watson: {data}")
        min_lon = float(data.get('min_lon'))
        min_lat = float(data.get('min_lat'))
        max_lon = float(data.get('max_lon'))
        max_lat = float(data.get('max_lat'))

        geojson = get_deforestation_geojson(min_lon, min_lat, max_lon, max_lat)

        url = "https://us-south.ml.cloud.ibm.com/ml/v1/deployments/cfea6c52-ae04-442f-8f94-0d196d0834ed/text/generation?version=2021-05-01"

        body = {
          "input": json.dumps(geojson),
          "parameters": {
            "max_new_tokens": 2000
          }
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer Placeholder"
        }

        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        watson_response = response.json()

        generated_text = watson_response['results'][0]['generated_text']

        # Extract coordinates from the geojson
        coordinates = geojson['features'][0]['geometry']['coordinates'][0]  # Assuming one polygon
        formatted_coords = '\n'.join([f"- Lon: {lon}, Lat: {lat}" for lon, lat in coordinates])
        affected_area_text = f"Affected Coordinates:\n{formatted_coords}\n\n"

        email_body = generated_text.replace("\n\nSincerely,", "")
        email_body = email_body.replace(
             "\n\n[Your Name]\n[Your Title]\n[Your Organization]",
             f"\n\n{affected_area_text}Sincerely,\nBytes For Bark Automated System"
        )

        # Create Content-ID for embedded image
        logo_cid = make_msgid(domain='example.com')

        # Compose HTML email body including the embedded logo image at the bottom
        html_body = f"""
        <html>
          <body>
            <pre style="font-family: monospace;">{email_body}</pre>
            <br>
            <img src="cid:{logo_cid[1:-1]}" alt="Bytes For Bark Logo" style="width:150px;"/>
          </body>
        </html>
        """

        msg = EmailMessage()
        msg['Subject'] = "Suspected Deforestation Alert"
        msg['From'] = 'Placeholder'
        msg['To'] = 'Placeholder'

        # Set plain text content and add HTML alternative with embedded image
        msg.set_content(email_body)
        msg.add_alternative(html_body, subtype='html')

        # Attach logo.png inline
        with open('logo.png', 'rb') as img:
            img_data = img.read()

        mime_type, _ = mimetypes.guess_type('logo.png')
        maintype, subtype = mime_type.split('/')

        # Attach the image to the HTML part (which is the second payload)
        msg.get_payload()[1].add_related(img_data, maintype=maintype, subtype=subtype, cid=logo_cid)

        # SMTP configuration and send email
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        smtp_user = 'Placeholder'
        smtp_pass = 'Placeholder'  # Use app password or env var for security

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logging.info("Watson response received successfully and email sent.")
        return jsonify(response.json())

    except requests.RequestException as re:
        logging.error(f"Watson API request failed: {re} - Response: {getattr(re.response, 'text', None)}")
        return jsonify({'error': 'Watson API request failed', 'details': str(re)}), 500
    except Exception as e:
        logging.exception("Error in /send_to_watson route")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting Flask app")
    app.run(debug=True)
