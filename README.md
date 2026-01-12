# eilken-harvard-portfolio

This data science portfolio contains a collection of projects developed as part of my graduate studies at **Harvard University Extension School** and through independent research. Each project highlights practical applications of data science techniques, ranging from clustering and dimensionality reduction to natural language processing.

---

## Projects

### 1. Hospital Bed Occupancy Forecasting
- **Course:** *CSCI E-116 Dynamic Modeling and Forecasting in Big Data*  
- **Description:** Comparative analysis of time series forecasting models for predicting weekly hospital bed occupancy at AdventHealth Orlando using 197 weeks of data (July 2020 – April 2024).  
- **Highlights:**
  - Evaluated multiple models: Structural State-Space, SARIMAX, VAR, LSTM, and Seasonal Naive baseline  
  - Structural State-Space model achieved best performance with 1.75% MAE and near-zero bias  
  - Implemented rolling forecast framework with hybrid retraining strategy  
  - Integrated external data sources (CDC flu rates, NOAA weather data) via feature engineering  
- [Project Repository](./hospital_forecasting_dynamic_modeling_project)

---

### 2. Stock Busters: An Agentic System for Stock Recommendations
- **Course:** *CSCI E-115 Advanced Practical Data Science*  
- **Description:** Developed a production-grade multi-agent AI system for personalized stock recommendations, combining quantamental analysis with RAG-powered reasoning and deployed on GCP, Google Kubernetes Engine.  
- **Highlights:**
  - Built end-to-end ML pipeline with Docker and GCP.
  - Deployed on Cloud Run Jobs with automated daily retraining via Cloud Scheduler  
  - Implemented quantamental model combining 30+ technical and fundamental indicators (Random Forest classifier)  
  - Deployed scalable application on GKE with CI/CD pipeline (70% code coverage, automated testing)  
  - Integrated RAG system with ChromaDB and Vertex AI for contextual stock reasoning  
  - Built Next.js frontend with conversational AI chatbot for personalized investment recommendations  
- [Project Repository](./stock_ai_agent_project)

---

### 3. Building an Intelligent Lakehouse with Databricks and Spark
- **Course:** *CSCI E-103 Data Engineering for Analytics*  
- **Description:** Designed and implemented a data lakehouse architecture using **Databricks and Spark** for store sales forecasting, featuring a complete ETL pipeline from raw data ingestion to ML model deployment.  
- **Highlights:**
  - Built bronze/silver/gold Delta Lake architecture with incremental streaming pipelines  
  - Implemented robust daily data pipelines with upserts and merges in the gold layer  
  - Deployed GBT Regressor model with MLflow lifecycle management (R² = 0.82 on validation set)  
  - Created Databricks SQL dashboard with security model using role-based access control  
- [Project Repository](./data_engineering_analytics_with_databricks_and_spark_project)

---

### 4. Data Mining Airline Delays for Clusters, Patterns, and Anomalies
- **Course:** *CSCI E-108 Data Mining*  
- **Description:** Analyzed the **ASA 2009 Airline On-Time Performance Dataset** using clustering (K-Means, DBSCAN, OPTICS, Agglomerative) and dimensionality reduction (PCA, UMAP, Spectral Embedding).  
- **Highlights:**
  - Identified delay patterns by routes, carriers, and airports  
  - Detected anomalies in flight delay structures  
  - Evaluated models using silhouette scores and Calinski-Harabasz index  
- [Project Repository](./data_mining_airline_delays_project)

---

### 5. NLP Sentiment Analysis of IMDb Reviews
- **Course:** *CSCI E-109B Advanced Topics in Data Science*  
- **Description:**
  - Developed a deep learning NLP model (BERT + BiLSTM model) that predicts review sentiments with ~90% accuracy and ~94% precision
  - Built and evaluated multiple NLP models for sentiment classification on IMDb movie reviews.  
- **Highlights:**
  - Preprocessing with tokenization, embeddings, and sequence padding  
  - Implemented models: Logistic Regression, Naive Bayes, LSTMs, and BERT  
  - Compared performance and discussed tradeoffs between classical ML and deep learning models  
- [Project Repository](./nlp_sentiment_analysis_project)  

---

## About me
I am a ***Master’s in Data Science candidate at Harvard University Extension School*** (graduating May 2026) with a strong foundation in machine learning, natural language processing, statistical modeling, and data engineering.

My experience spans building end-to-end ML pipelines, applying clustering and dimensionality reduction techniques for large datasets, and developing deep learning models for NLP and forecasting. I have hands-on expertise with modern tools such as Python, R, SQL, Spark, TensorFlow, PyTorch, GCP, AWS, and Databricks, and I focus on translating complex datasets into scalable, real-world solutions.

This portfolio highlights projects that combine academic rigor with practical applications, ranging from predictive modeling in healthcare to airline delay analytics, MLOps deployment, data engineering, and dynamic time series forecasting.

This repository demonstrates my technical and analytical skills across multiple areas of data science. 


**Contact:** 

noe489@g.harvard.edu

[Noah Eilken's LinkedIn](www.linkedin.com/in/neilken)

