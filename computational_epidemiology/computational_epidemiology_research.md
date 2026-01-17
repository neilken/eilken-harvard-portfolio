# ***H5N1 Computational Epidemiology & Early-Warning System (In Progress)***
### *Data Science and AI Meet Public Health*

## Overview
This project explores whether large-scale social media signals can provide early-warning indicators for global H5N1 (avian influenza) outbreaks. It integrates multilingual social media data with official outbreak surveillance sources to evaluate whether digital signals lead or complement traditional reporting.

Developed as a master’s-level ***Capstone Research Project in Data Science*** at Harvard University Extension School, the work focuses on applied computational digital epidemiology, time-series forecasting, and scalable, real-world deployment. The goal is to use data science and AI to improve real-world public health early-warning and decision-making systems.

**Status:** Actively in development.

---

## Problem Statement
Traditional H5N1 surveillance relies on clinical and laboratory reporting from organizations such as the WHO and FAO. These reports are accurate but delayed. This project tests whether public digital signals from platforms like Meta (Facebook/Instagram) and X (Twitter) can improve **timeliness and situational awareness** for outbreak detection.

---

## Data Sources
- **Social Media**
  - Meta platforms (Facebook, Instagram)
  - X (Twitter)
- **Official Surveillance**
  - World Health Organization (WHO)
  - Food and Agriculture Organization (FAO)
  - ProMED-mail outbreak reports

Data are processed at temporal and geographic resolutions suitable for time-series modeling and lead-time analysis.

---

## Methods
- **Data Engineering**
  - Scalable ingestion and preprocessing pipelines
  - Temporal alignment between social media signals and outbreak reports

- **Natural Language Processing**
  - Multilingual text normalization and translation
  - Sentiment and signal intensity extraction
  - Filtering of non-epidemiological and noisy content

- **Time-Series Analysis & Forecasting**
  - Lag and lead-time analysis between digital signals and confirmed outbreaks
  - Baseline comparisons against traditional surveillance timelines
  - Evaluation of signal reliability across regions and platforms

---

## Project Goals
- Quantify whether social media signals precede official outbreak reports
- Measure variability in lead-time across languages and regions
- Evaluate tradeoffs between early detection and false alarms
- Design a prototype **early-warning decision-support system**

---

## Preliminary Observations
- Early exploratory analysis suggests social media activity may exhibit detectable shifts prior to some official reports.
- Signal strength and reliability vary by platform, language, and geography.
- Further modeling and validation are ongoing.

Final results will be reported upon project completion.

---

## Tech Stack
- Python
- Pandas, NumPy
- NLP libraries (transformer-based models)
- Time-series modeling frameworks
- Cloud-ready pipeline design


---

## Use Cases
- Digital epidemiology research
- Public health situational awareness
- Early-warning system prototyping
- Multilingual NLP for health surveillance

---

## Author
Noah Eilken  
Data Scientist | Health Analytics | Forecasting & NLP

## Contact
Email: noe489@g.harvard.edu 

LinkedIn: https://www.linkedin.com/in/neilken
