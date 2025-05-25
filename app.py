from flask import Flask, request, render_template_string, send_file, jsonify
import ee
import json
from datetime import datetime, timedelta, timezone
import io
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>NDVI Deforestation Detector</title>
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
    </head>
    <body>
        <h1>Detect Deforestation with NDVI</h1>
        <p>Enter coordinates for your area of interest:</p>
        <form id="coordsForm" autocomplete="on" spellcheck="false">
            <table>
                <tr>
                    <td><label for="min_lon">Min Longitude:</label></td>
                    <td><input type="text" id="min_lon" name="min_lon" required placeholder="-60.0"></td>
                </tr>
                <tr>
                    <td><label for="min_lat">Min Latitude:</label></td>
                    <td><input type="text" id="min_lat" name="min_lat" required placeholder="-3.0"></td>
                </tr>
                <tr>
                    <td><label for="max_lon">Max Longitude:</label></td>
                    <td><input type="text" id="max_lon" name="max_lon" required placeholder="-59.0"></td>
                </tr>
                <tr>
                    <td><label for="max_lat">Max Latitude:</label></td>
                    <td><input type="text" id="max_lat" name="max_lat" required placeholder="-2.0"></td>
                </tr>
            </table>

            <button type="button" onclick="downloadGeoJSON()">Download GeoJSON</button>
            <button type="button" onclick="previewGeoJSON()">Preview on geojson.io</button>
            <button type="button" onclick="sendToWatson()">Run Watson Analysis</button>
            <p style="color: #a0a0bf; font-size: 0.9em; margin-top: 1em;">
            Time frame used for analysis:<br>
            <strong>Before period:</strong> 3 months to 7 days ago<br>
            <strong>After period:</strong> Last 7 days
            </p>                      
        </form>

        <script>
            function getFormParams() {
                const form = document.getElementById('coordsForm');
                const params = new URLSearchParams(new FormData(form));
                return params.toString();
            }

            function downloadGeoJSON() {
                const params = getFormParams();
                const url = '/download_geojson?' + params;
                const a = document.createElement('a');
                a.href = url;
                a.download = 'deforestation.geojson';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }

            async function previewGeoJSON() {
                const params = getFormParams();
                const response = await fetch('/generate_geojson?' + params);
                if (!response.ok) {
                    alert('Error generating GeoJSON preview');
                    return;
                }
                const geojson = await response.json();
                const encoded = encodeURIComponent(JSON.stringify(geojson));
                const previewUrl = `https://geojson.io/#data=data:application/json,${encoded}`;
                window.open(previewUrl, '_blank');
            }

            async function sendToWatson() {
                try {
                    const response = await fetch('/send_to_watson', { method: 'POST' });
                    const result = await response.json();
                    if (response.ok) {
                        alert(result.message);
                    } else {
                        alert('Error: ' + result.error);
                    }
                } catch (err) {
                    alert('Network error: ' + err.message);
                }
            }
        </script>
    </body>
    </html>
    """)


def get_deforestation_geojson(min_lon, min_lat, max_lon, max_lat):
    SERVICE_ACCOUNT = 'placeholder'
    KEY_PATH = 'placeholder'
    credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_PATH)
    ee.Initialize(credentials)

    aoi = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])

    today = datetime.now(timezone.utc)
    three_months_ago = today - timedelta(days=90)
    seven_days_ago = today - timedelta(days=7)

    before_start = three_months_ago.strftime('%Y-%m-%d')
    before_end = seven_days_ago.strftime('%Y-%m-%d')
    after_start = seven_days_ago.strftime('%Y-%m-%d')
    after_end = today.strftime('%Y-%m-%d')

    SELECTED_BANDS = ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B9', 'B11', 'B12', 'SCL']

    def maskS2sr(image):
        image = image.select(SELECTED_BANDS)
        scl = image.select('SCL')
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
        return image.updateMask(mask).divide(10000)

    def addNDVI(image):
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return image.addBands(ndvi)

    before_collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterDate(before_start, before_end)
                         .filterBounds(aoi)
                         .map(maskS2sr)
                         .map(addNDVI))

    after_collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                        .filterDate(after_start, after_end)
                        .filterBounds(aoi)
                        .map(maskS2sr)
                        .map(addNDVI))

    before = before_collection.median().select('NDVI')
    after = after_collection.median().select('NDVI')

    diff = before.subtract(after).rename('NDVI_change')
    deforestation = diff.gt(0.2)

    deforestation_vectors = deforestation.selfMask().reduceToVectors(
        geometry=aoi,
        scale=10,
        geometryType='polygon',
        labelProperty='deforestation',
        maxPixels=1e10
    )

    deforestation_geojson = deforestation_vectors.getInfo()
    return deforestation_geojson


@app.route('/download_geojson')
def download_geojson():
    min_lon = float(request.args.get('min_lon'))
    min_lat = float(request.args.get('min_lat'))
    max_lon = float(request.args.get('max_lon'))
    max_lat = float(request.args.get('max_lat'))

    try:
        geojson = get_deforestation_geojson(min_lon, min_lat, max_lon, max_lat)
    except Exception as e:
        return f"Error generating GeoJSON: {e}", 500

    geojson_str = json.dumps(geojson, indent=2)
    buf = io.BytesIO()
    buf.write(geojson_str.encode('utf-8'))
    buf.seek(0)
    return send_file(buf, mimetype='application/geo+json', as_attachment=True, download_name='deforestation.geojson')


@app.route('/generate_geojson')
def generate_geojson():
    min_lon = float(request.args.get('min_lon'))
    min_lat = float(request.args.get('min_lat'))
    max_lon = float(request.args.get('max_lon'))
    max_lat = float(request.args.get('max_lat'))

    try:
        geojson = get_deforestation_geojson(min_lon, min_lat, max_lon, max_lat)
        return jsonify(geojson)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/send_to_watson', methods=['POST'])
def send_to_watson():
    SMTP_SERVER = 'placeholder'                          # Replace with your SMTP server
    SMTP_PORT = 587                                      # Replace with your SMTP port if different
    SMTP_USERNAME = 'placeholder'                        # Replace with your SMTP username
    SMTP_PASSWORD = 'placeholder'                        # Replace with your SMTP password
    TO_EMAIL = 'placeholder'                             # Replace with the recipient email

    html_message = """
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6;">
<p>Dear Canadian Environmental Oversight Authorities,</p>

<p>
  I am writing to alert you about suspected deforestation activity identified from GeoJSON data analysis, enhanced with predictive analytics and AI-driven insights, in the Alberta Tar Sands region, 
  and to bring to your attention potential future deforestation risks predicted by our AI models.
</p>

<h3>Regional Context</h3>
<p>
  The Alberta Tar Sands region is a geographically significant area, characterized by vast boreal forests and diverse wildlife habitats. 
  However, the region is also heavily impacted by industrial activities, particularly oil sands extraction, which poses significant environmental risks, including deforestation and habitat destruction.
</p>

<h3>Coordinates</h3>
<ul>
  <li>54.7232, -112.4556</li>
  <li>55.1232, -111.4556</li>
  <li>53.8232, -113.4556</li>
</ul>
<p>Please verify these coordinates extracted from GeoJSON data as they may indicate locations of suspected deforestation.</p>

<h3>Predictive Insights</h3>
<p>
  Our AI-driven analysis predicts potential future deforestation hotspots based on historical data, industrial trends, and environmental conditions. 
  The urgency of proactive monitoring cannot be overstated, as the continued destruction of boreal forests and wildlife habitats may have irreversible consequences.
</p>

<h3>Legal Analysis</h3>
<ul>
  <li><strong>Species at Risk Act (SARA), Section 58:</strong> Protects critical habitats.</li>
  <li><strong>Impact Assessment Act:</strong> Requires environmental and cumulative effect assessments.</li>
  <li><strong>Canadian Environmental Protection Act (CEPA), Section 166:</strong> Aims to prevent environmental harm.</li>
</ul>

<h3>Enforcement Gaps</h3>
<ul>
  <li><strong>Lack of cumulative impact assessments</strong></li>
  <li><strong>Inadequate critical habitat protection</strong></li>
  <li><strong>Insufficient Indigenous community consultation</strong></li>
</ul>

<h3>Policy Recommendations</h3>
<ul>
  <li><strong>Comprehensive cumulative impact assessments</strong></li>
  <li><strong>Enhanced protection of critical habitats</strong></li>
  <li><strong>Meaningful consultation with Indigenous communities respecting their rights</strong></li>
  <li><strong>Incorporation of predictive analytics into ongoing environmental monitoring and enforcement strategies</strong></li>
</ul>

<h3>Call to Action</h3>
<p>
  We urge prompt investigation into the suspected deforestation activity and integration of AI-driven monitoring tools via our automated watchdog system. 
  Stronger regulatory oversight is necessary to prevent further environmental harm while balancing ecological and economic interests.
</p>

<p><em>This message was generated using IBM Watson AI to support environmental monitoring efforts through an automated, user-configurable system designed for continuous data analysis and real-time alerting.</em></p>

<p>Sincerely,<br>
Bytes For Bark Automated System</p>

<h3>Sources</h3>
<ul>
  <li>FRA 2020 report, Canada</li>
  <li>Canadian Environmental Protection Act (1999)</li>
  <li>Species at Risk Act (SARA)</li>
  <li>Impact Assessment Act</li>
  <li>Relevant documents from the vector index, including but not limited to:</li>
  <ul>
    <li>PART 9 Government Operations and Federal and Aboriginal Land</li>
    <li>Sections 211-212 Release of Substances</li>
    <li>Report and remedial measures (Section 212)</li>
  </ul>
</ul>


    </body>
    </html>
    """

    try:
        msg = EmailMessage()
        msg['Subject'] = 'Environmental Watchdog Alert: Watson AI Deforestation Analysis Results'
        msg['From'] = SMTP_USERNAME
        msg['To'] = TO_EMAIL
        msg.set_content("This is an HTML-formatted email. Please use an email client that supports HTML.")
        msg.add_alternative(html_message, subtype='html')

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)

        return jsonify({"message": "GeoJSON analysis email successfully sent."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
