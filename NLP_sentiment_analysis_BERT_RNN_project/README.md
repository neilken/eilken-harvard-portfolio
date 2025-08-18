# Sentiment Analysis with NLP on IMDb Reviews
##### *CSCI E-109B – Data Science Final Project*
##### *Harvard University Extension School*
##### *Noah Eilken, Master’s Candidate in Data Science*

---

## Project Overview
This project applies **Natural Language Processing (NLP)** techniques to classify IMDb movie reviews as positive or negative. Both classical machine learning and deep learning approaches were explored, with a focus on evaluating accuracy and model trade-offs. 

***We developed a deep learning NLP model (BERT + BiLSTM model) that predicts review sentiments with ~90% accuracy and ~94% precision***

---

## Methods
- **Preprocessing**: Tokenization, stopword removal, lemmatization, sequence padding  
- **Classical Models**: Logistic Regression, Naïve Bayes, Support Vector Machines (SVM)  
- **Deep Learning Models**: RNN/LSTM, BERT + LSTM 
- **Evaluation**: Accuracy, Precision/Recall, F1 Score, Confusion Matrix  

---

## Key Results
- Naive Bayes, Logistic Regression, and SVM provided strong baselines with TF-IDF features  
- BERT + LSTM model outperforms classical models, achieving a validation accuracy of ~90%, with a precision of ~94%, a recall of ~86%, an F1 score of ~90%, and an AUC score of 0.97
- Trade-offs observed between model complexity, training time, and interpretability  

---

## Dataset
- **Source**: [IMDb Movie Reviews Dataset](https://ai.stanford.edu/~amaas/data/sentiment/)  
- 50,000 labeled reviews (25k training, 25k testing)  
- Binary classification: *positive* or *negative*  

---

## Tech Stack
Python, Pandas, NumPy, Scikit-learn, TensorFlow/Keras, NLTK, spaCy  
