# Mining Airline Delays for Anomalies and Clusters

## Project Overview
This project analyzes the **2009 ASA Airline On-Time Performance dataset** to uncover patterns in flight delays. Using clustering and dimensionality reduction techniques, it identifies groups of routes with similar delay behaviors and highlights anomalous patterns.  

---

## Objectives
- Aggregate flight-level data into route-level delay profiles  
- Apply PCA and Spectral Embeddings for dimensionality reduction  
- Cluster routes using K-Means, DBSCAN, OPTICS, and Agglomerative Clustering  
- Evaluate models with Silhouette Score and Calinski-Harabasz Index  
- Interpret clusters in terms of route volume, distance, and delay causes  

---

## Methods
- **Preprocessing:** Removed canceled/diverted flights, filtered carriers, handled missing values  
- **Feature Engineering:** Route-level averages of delay types, distance, and flight volume  
- **Dimensionality Reduction:** PCA, Spectral Embedding, UMAP  
- **Clustering:** K-Means, DBSCAN, OPTICS, Agglomerative  
- **Evaluation:** Silhouette Score, Calinski-Harabasz Index, visualizations  

---

## Key Results
- K-Means with Spectral Embeddings revealed clear clusters by distance and flight volume  
- DBSCAN identified anomalous routes with extreme delay profiles  
- Agglomerative Clustering produced two main groups: short, high-volume routes vs. longer, low-volume routes  
- Distance and flight volume strongly influenced clustering results  

---

## Dataset
- **Source:** Airline On-Time Performance Data (2004–2008), hosted on the Harvard Dataverse  
- Due to size, the raw data is not included in this repository.  
- You can access the dataset here: [Harvard Dataverse – Airline On-Time Performance](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/HG7NV7)  

---

## Tech Stack
- Python (pandas, NumPy, matplotlib, seaborn)  
- Scikit-learn (PCA, clustering, evaluation metrics)  
- UMAP, SpectralEmbedding  

---

## Author
**Noah Eilken**  
Data Science Master's Degree Candidate, Harvard University Extension School  
