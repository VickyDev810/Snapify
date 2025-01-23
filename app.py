from flask import Flask, request, jsonify
from transformers import BlipProcessor, BlipForConditionalGeneration, pipeline
from PIL import Image
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import os
import random


# Load environment variables
load_dotenv()

api_key = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')

# Initialize Flask app
app = Flask(__name__)

# Initialize models and Spotify client
model_name = "Salesforce/blip-image-captioning-base"
processor = BlipProcessor.from_pretrained(model_name)
model = BlipForConditionalGeneration.from_pretrained(model_name)
emotion_model = pipeline("text-classification", model="bhadresh-savani/bert-base-uncased-emotion")

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=api_key, client_secret=api_secret))

# Genre mapping function
def map_emotion_to_genre(emotion):
    genre_mapping = {
        "joy": ["pop", "dance", "happy", "upbeat", "party"],
        "sadness": ["blues", "acoustic", "sad pop", "melancholy", "chill"],
        "anger": ["rock", "metal", "punk", "grunge"],
        "fear": ["ambient", "soundtrack", "horror", "darkwave"],
        "surprise": ["upbeat", "pop", "indie", "funk"],
        "disgust": ["industrial", "gothic", "metal"],
        "party": ["electronic", "house", "dance", "techno", "party"]
    }
    return genre_mapping.get(emotion, ["pop"])

# Search for songs using Spotify API
def search_songs_by_genre(genre):
    # Search for songs by genre
    results = sp.search(q=f'genre:{genre}', limit=50, type='track')
    
    # Keywords to exclude Hindi or Indian songs
    exclude_keywords = ['bollywood', 'hindi', 'punjabi', 'india', 'indian', 'desi', 'stree', 'anuv jain',  'vishal mishra']
    
    songs = []
    for track in results['tracks']['items']:
        song_info = {
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'uri': track['uri']
        }
        
        # Check if the track name or artist name contains any of the exclude keywords
        if any(keyword.lower() in song_info['name'].lower() or keyword.lower() in song_info['artist'].lower() for keyword in exclude_keywords):
            continue  # Skip the song if it contains an excluded keyword
        
        # If not excluded, add to the list
        songs.append(song_info)
    
    return songs

# Route to get the connected Spotify account details
@app.route('/account', methods=['GET'])
def get_account():
    try:
        # Fetch current user's Spotify account info
        user_info = sp.current_user()
        return jsonify({
            "account": user_info['display_name'],
            "id": user_info['id'],
            "uri": user_info['uri']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/generate-caption', methods=['POST'])
def generate_caption():
    try:
        # Receive and save the image
        image_file = request.files['image']
        image = Image.open(image_file).convert("RGB")
        
        # Generate caption
        inputs = processor(images=image, return_tensors="pt")
        output = model.generate(**inputs)
        caption = processor.decode(output[0], skip_special_tokens=True)
        
        return jsonify({"caption": caption})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/analyze-emotion', methods=['POST'])
def analyze_emotion():
    try:
        # Extract caption from the request
        data = request.json
        caption = data.get('caption', '')
        
        # Analyze emotion
        result = emotion_model(caption)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/recommend-songs', methods=['POST'])
def recommend_songs():
    try:
        # Extract caption from the request
        data = request.json
        caption = data.get('caption', '')
        
        # Analyze emotion
        emotions = emotion_model(caption)
        dominant_emotion = max(emotions, key=lambda e: e['score'])
        
        if dominant_emotion['score'] < 0.2:
            return jsonify({"error": "Emotion detection confidence too low."}), 400
        
        emotion_label = dominant_emotion['label']
        genres = map_emotion_to_genre(emotion_label)[:1]
        
        # Fetch some random songs from the genre
        recommended_songs = []
        for genre in genres:
            songs = search_songs_by_genre(genre)
            random_songs = random.sample(songs, min(5, len(songs)))  # Randomize the selection
            recommended_songs.extend(random_songs)
        
        return jsonify({"songs": recommended_songs})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# Run Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
