from PIL import Image
from flask import Flask, render_template, request, redirect
from skimage import io as skio
import numpy as np
import pickle
import io
import base64
import matplotlib.pyplot as plt
import matplotlib
import cv2
matplotlib.use('Agg')
import os
import validators
from io import BytesIO
import requests

app = Flask(__name__)

# Load the clustering model
def load_clustering_model():
    file_path = os.path.join(os.path.dirname(__file__), 'colormodel.pkl')
    with open(file_path, 'rb') as model_file:
        return pickle.load(model_file)

# Default K value for the model
default_k = 5  # You can change this to your preferred default K value

clustering_model = load_clustering_model()

def get_image_from_url(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()  # Check for successful response
        image_content = BytesIO(response.content)
        img = Image.open(image_content)
        img_array = np.array(img)
        return img_array
    except requests.exceptions.RequestException as e:
        print(f"Request error while fetching image: {str(e)}")
        return None
    except Exception as e:
        print(f"Error fetching or processing image from URL: {str(e)}")
        return None

def process_image(file, k):
    if validators.url(file):
        img = get_image_from_url(file)
        if img is None:
            return None, None, None
    else:
        img = skio.imread(file)

    original_image = img.copy()
    img = cv2.resize(img, (50, 50))
    img = img.reshape((img.shape[0] * img.shape[1], img.shape[2]))

    clustering_model.n_clusters = k
    cluster_labels = clustering_model.fit_predict(img)

    hist, _ = np.histogram(cluster_labels, bins=np.arange(0, len(np.unique(cluster_labels)) + 1))
    hist = hist.astype("float")
    hist /= hist.sum()

    cluster_centers = clustering_model.cluster_centers_.astype(int)
    percentages = (hist * 100).round(2)
    colors_with_percentages = [(f'rgb({c[0]}, {c[1]}, {c[2]})', p) for c, p in zip(cluster_centers, percentages)]

    hist_bar = np.zeros((50, 400, 3), dtype="uint8")
    startX = 0
    for (percent, color) in zip(hist, clustering_model.cluster_centers_):
        endX = startX + (percent * 400)
        cv2.rectangle(hist_bar, (int(startX), 0), (int(endX), 50), color.astype("uint8").tolist(), -1)
        startX = endX

    chart_buffer = io.BytesIO()
    plt.figure(figsize=(6, 2))
    plt.imshow(hist_bar)
    plt.axis('off')  # Turn off axis
    plt.savefig(chart_buffer, format='png', bbox_inches='tight', pad_inches=0)
    chart_buffer.seek(0)
    chart_base64 = base64.b64encode(chart_buffer.read()).decode()
    plt.close()

    return original_image, colors_with_percentages, chart_base64

@app.route('/')
def index():
    return render_template('index.html', result=None, default_k=default_k)

@app.route('/upload', methods=['POST'])
def upload():
    image = request.files['image']
    if image.filename == '':
        image = request.form.get('image_url')
        if image == '':
            return "You have not uploaded an image nor provided a link to one"

    k = int(request.form.get('k', default_k))
    img, colors_with_percentages, chart_base64 = process_image(image, k)

    if img is None:
        return "Error processing the image"

    img_buffer = io.BytesIO()
    if img.shape[2] == 4:  # Check if the image has an alpha channel
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)  # Convert RGBA to RGB

    skio.imsave(img_buffer, img, format="JPEG")
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode()

    result = {
        'image_base64': img_base64,
        'colors': colors_with_percentages,
        'chart_base64': chart_base64
    }

    return render_template('index.html', result=result, default_k=default_k)

if __name__ == '__main__':
    app.run(debug=True)
