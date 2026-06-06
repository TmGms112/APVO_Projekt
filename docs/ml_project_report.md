# APVO Music Recommendation System Report Notes

## 1. Problem Definition

The application is extended with analytical functionality for a personal music library. The problem is to recommend the next song and generate playlists of similar songs from audio files uploaded by the user. This is a content-based recommendation problem because the system uses properties extracted from the uploaded audio files rather than external ratings or prepared datasets.

## 2. Data Source

The data is live user-generated data. Each song is uploaded through the frontend and stored in MongoDB GridFS. Existing legacy songs can also be read from MinIO object storage when their MongoDB records contain `file_key` and `bucket`. The metadata and extracted analytical fields are stored in the MongoDB `songs` collection. This satisfies the requirement to use original data rather than a prepared dataset.

Stored data includes:

- title and artist
- uploaded file id in GridFS or legacy object-storage key
- file size and upload timestamp
- analysis status
- hash values for duplicate detection
- extracted audio metadata
- extracted machine-learning fields
- selected model cluster after training

Hash values are stored for duplicate detection and reporting, but they are explicitly excluded from model training and recommendation vectors.

## 3. Data Processing Pipeline

1. User uploads an audio file from the React frontend.
2. FastAPI stores the file directly in MongoDB GridFS.
3. A worker process finds songs that are pending or missing extracted ML features.
4. The worker reads the audio bytes from GridFS or legacy MinIO storage.
5. The worker extracts audio features with Librosa and metadata with TinyTag.
6. The worker stores the analytical song fields in MongoDB.
7. The ML endpoint builds a training matrix from analyzed song fields, excluding hash values, hash-derived duplicate flags, storage references, technical IDs and timestamps.
8. Numeric fields are robust-scaled, acoustic analysis features are weighted higher than noisy text metadata, high-cardinality text fields are encoded as compact text/frequency features, and PCA reduces noise in the model space.
9. The ML endpoint trains and compares models across several candidate cluster counts. For medium and large libraries, two-cluster results are not considered because they do not create useful playlists.
10. The best model assigns each song to a cluster used as an automatic playlist.
11. Cosine similarity is used to recommend the next song from the same non-hash feature schema.

## 4. Fields Used By The Models

The model input is built from analyzed song data:

- extracted audio features, including tempo, energy, spectral, MFCC and chroma values
- file attributes such as file size and duration
- parsed audio metadata such as bitrate, sample rate, channel count and year
- categorical metadata such as title, artist, album, genre, filename and content type

High-cardinality categorical fields such as song titles are not expanded into huge sparse one-hot vectors. Instead, the app uses compact text statistics such as known/missing state, text length, token count and value frequency. Low-cardinality categorical fields can still use one-hot values. This keeps all useful non-hash song data available without letting sparse metadata dominate audio similarity.

Excluded model fields:

- `hash`
- `md5_hash`
- hash-derived duplicate fields such as `is_duplicate` and `duplicate_of`
- technical identifiers such as MongoDB `_id`, GridFS `file_id`, object-storage `file_key`, and storage bucket names
- timestamps and previous ML output fields

This keeps the model based on the user's analyzed song data without allowing file hashes or storage implementation details to influence similarity.

## 5. Models Tested

### Model 1: K-Means Clustering

K-Means divides songs into clusters by minimizing distance between songs and their cluster center. It is useful for playlist generation because every cluster becomes a group of songs around a representative centroid. The app tests multiple cluster counts and keeps the K-Means result with the best combined playlist-usefulness score.

### Model 2: Gaussian Mixture Model

Gaussian Mixture clustering creates probabilistic song groups. Unlike K-Means, it can represent clusters with different shapes and spreads, so it is a useful comparison model for music libraries where some playlists may be broad while others are more compact. The app tests multiple cluster counts and covariance settings, then keeps the best Gaussian Mixture result.

### Recommendation Layer: Cosine Similarity

Cosine similarity is used for the next-song recommendation. After the model fields are processed through the same non-hash feature pipeline, the app compares the currently selected song to every other analyzed song and returns the most similar songs. This is not the main evaluated model; it is the retrieval layer that uses the same feature schema as the trained models.

## 6. Evaluation Metrics

The app computes three clustering metrics:

- Silhouette Score: higher is better. It measures how well songs fit inside their cluster compared with other clusters.
- Davies-Bouldin Score: lower is better. It measures cluster compactness and separation.
- Calinski-Harabasz Score: higher is better. It compares between-cluster separation with within-cluster dispersion.

The app also computes playlist-balance metrics:

- maximum playlist fraction: the percent of trained songs in the largest generated playlist
- playlist balance score: normalized entropy of cluster sizes, where higher means songs are spread more evenly
- minimum and maximum playlist sizes

The selected model is chosen by a playlist-usefulness score. This score still rewards silhouette quality, but it also rewards balanced playlist sizes and penalizes results where one playlist contains most songs. This is important because the goal is not only mathematical clustering quality, but usable playlists in the app.

## 7. Application Functionality

The frontend includes a Machine Learning section with:

- Train Models button
- Load ML Dashboard button
- model comparison chart
- selected model metrics
- maximum playlist size metric
- tempo, energy and duration distributions
- generated playlists with Play buttons
- automatic playback through the playlist queue
- next-song recommendations from the song list

The song list has a Next button for analyzed songs. Clicking it calls `GET /ml/recommendations/{song_id}` and displays the most similar songs. Generated playlists can be played from the dashboard, and the sticky audio player advances to the next song in the selected playlist.

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
- largest playlist fraction
- number of model input fields used by the selected run
- PCA dimensions and explained variance from the selected model run

For the paper, include a table like this after running the model on your real songs:

| Model | Silhouette Score | Davies-Bouldin Score | Calinski-Harabasz Score | Playlists | Largest Playlist | Selected |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| K-Means | value from dashboard | value from dashboard | value from dashboard | value from dashboard | value from dashboard | yes/no |
| Gaussian Mixture | value from dashboard | value from dashboard | value from dashboard | value from dashboard | value from dashboard | yes/no |

## 9. Suggested Presentation Text

This project implements a personal music recommendation system. The system uses MongoDB as a NoSQL database for metadata and new audio file storage through GridFS, while maintaining compatibility with older MinIO-backed song files. After each upload, a background worker extracts audio features and metadata from the song. The machine-learning pipeline builds model vectors from analyzed song data while excluding hash values, technical identifiers, storage references and timestamps. The preprocessing step uses robust scaling, compact metadata encoding, acoustic feature weighting and PCA denoising. Two clustering models, K-Means and Gaussian Mixture clustering, are evaluated using silhouette score, Davies-Bouldin score, Calinski-Harabasz score and playlist-balance metrics. The best model is integrated into the application to create automatic playable playlists. For next-song recommendation, the system uses cosine similarity between processed non-hash song vectors to find the most similar uploaded songs.

## 10. Limitations And Future Work

The current approach is content-based and does not use listening history or ratings. The quality of the recommendations depends on the number and variety of uploaded songs. Future improvements could include user feedback, collaborative filtering, genre classification, or automatic playlist names generated from detected mood and tempo.
