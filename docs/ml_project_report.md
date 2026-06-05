# APVO Music Recommendation System Report Notes

## 1. Problem Definition

The application is extended with analytical functionality for a personal music library. The problem is to recommend the next song and generate playlists of similar songs from audio files uploaded by the user. This is a content-based recommendation problem because the system uses properties extracted from the uploaded audio files rather than external ratings or prepared datasets.

## 2. Data Source

The data is live user-generated data. Each song is uploaded through the frontend and stored in MongoDB GridFS. The metadata and extracted analytical fields are stored in the MongoDB `songs` collection. This satisfies the requirement to use original data rather than a prepared dataset.

Stored data includes:

- title and artist
- uploaded file id in GridFS
- file size and upload timestamp
- analysis status
- hash values for duplicate detection
- extracted audio metadata
- extracted machine-learning feature vector
- selected model cluster after training

## 3. Data Processing Pipeline

1. User uploads an audio file from the React frontend.
2. FastAPI stores the file directly in MongoDB GridFS.
3. A worker process finds songs with `analysis_status = pending`.
4. The worker reads the audio bytes from GridFS.
5. The worker extracts audio features with Librosa and metadata with TinyTag.
6. The worker stores the feature vector in MongoDB.
7. The ML endpoint trains and compares models on all analyzed songs.
8. The best model assigns each song to a cluster used as an automatic playlist.
9. Cosine similarity is used to recommend the next song from the feature vectors.

## 4. Extracted Features

The feature vector contains audio descriptors that summarize rhythm, loudness, timbre and harmonic content:

- duration in seconds
- tempo in BPM
- RMS energy mean and standard deviation
- zero crossing rate mean
- spectral centroid mean and standard deviation
- spectral bandwidth mean
- spectral rolloff mean
- spectral contrast mean
- 13 MFCC mean values
- 12 chroma mean values

These features are suitable because similar songs often share tempo, energy, spectral shape, timbre and harmonic profile.

## 5. Models Tested

### Model 1: K-Means Clustering

K-Means divides songs into a predefined number of clusters by minimizing distance between songs and their cluster center. It is useful for generating playlists because every cluster can be interpreted as a group of similar songs.

### Model 2: Agglomerative Clustering

Agglomerative Clustering starts with each song as its own cluster and repeatedly merges the most similar clusters. It is useful for small music libraries because it can form groups based on hierarchical similarity.

### Recommendation Layer: Cosine Similarity

Cosine similarity is used for the next-song recommendation. After the feature vectors are standardized, the app compares the currently selected song to every other song and returns the most similar songs. This is not the main evaluated model; it is the retrieval layer that uses the learned/extracted feature representation.

## 6. Evaluation Metrics

The app computes three clustering metrics:

- Silhouette Score: higher is better. It measures how well songs fit inside their cluster compared with other clusters.
- Davies-Bouldin Score: lower is better. It measures cluster compactness and separation.
- Calinski-Harabasz Score: higher is better. It compares between-cluster separation with within-cluster dispersion.

The selected model is the one with the highest silhouette score. Davies-Bouldin is used as a tie-breaker.

## 7. Application Functionality

The frontend includes a Machine Learning section with:

- Train Models button
- Load ML Dashboard button
- model comparison chart
- selected model metrics
- tempo, energy and duration distributions
- generated playlists
- next-song recommendations from the song list

The song list has a Next button for analyzed songs. Clicking it calls `GET /ml/recommendations/{song_id}` and displays the most similar songs.

## 8. Statistics And Charts For Presentation

Use the ML dashboard screenshots and the `/ml/stats` endpoint to present:

- total uploaded songs
- number of analyzed songs
- number of duplicates
- average tempo
- average energy
- average duration
- tempo histogram
- energy histogram
- duration histogram
- model comparison metrics
- generated cluster/playlist sizes

For the paper, include a table like this after running the model on your real songs:

| Model | Silhouette Score | Davies-Bouldin Score | Calinski-Harabasz Score | Selected |
| --- | ---: | ---: | ---: | --- |
| K-Means | value from dashboard | value from dashboard | value from dashboard | yes/no |
| Agglomerative Clustering | value from dashboard | value from dashboard | value from dashboard | yes/no |

## 9. Suggested Presentation Text

This project implements a personal music recommendation system. The system uses MongoDB as a NoSQL database for both metadata and audio file storage through GridFS. After each upload, a background worker extracts audio features from the song. Two clustering models, K-Means and Agglomerative Clustering, are evaluated using silhouette score, Davies-Bouldin score and Calinski-Harabasz score. The best model is integrated into the application to create automatic playlists. For next-song recommendation, the system uses cosine similarity between standardized audio feature vectors to find the most similar uploaded songs.

## 10. Limitations And Future Work

The current approach is content-based and does not use listening history or ratings. The quality of the recommendations depends on the number and variety of uploaded songs. Future improvements could include user feedback, collaborative filtering, genre classification, or automatic playlist names generated from detected mood and tempo.
