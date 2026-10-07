# BankGuard

BankGuard is an end-to-end fraud detection and transaction risk management platform.

The project combines machine learning, explainable AI, backend APIs, databases, real-time transaction monitoring, fraud alerts, investigation workflows, and MLOps to simulate how a modern fraud detection system can be designed.

---

## Table of Contents

- [Overview](#overview)
- [Project Goals](#project-goals)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Development Phases](#project-development-phases)
- [Current Progress](#current-progress)
- [Phase 1 — Project Foundation](#phase-1--project-foundation)
- [Phase 2 — Fraud ML Pipeline](#phase-2--fraud-ml-pipeline)
- [Dataset](#dataset)
- [Exploratory Data Analysis](#exploratory-data-analysis)
- [Data Preprocessing](#data-preprocessing)
- [Feature Engineering](#feature-engineering)
- [Model Training](#model-training)
- [Model Evaluation](#model-evaluation)
- [Risk Scoring](#risk-scoring)
- [SHAP Explainability](#shap-explainability)
- [ML Artifacts](#ml-artifacts)
- [Project Structure](#project-structure)
- [Phase 3 — MLflow](#phase-3--mlflow)
- [Future Architecture](#future-architecture)
- [Future Development](#future-development)
- [Installation](#installation)
- [Environment Setup](#environment-setup)
- [Running the Project](#running-the-project)
- [Git and Data Policy](#git-and-data-policy)
- [Development Roadmap](#development-roadmap)
- [Project Objective](#project-objective)

---

# Overview

Financial fraud detection is a highly imbalanced machine learning problem where fraudulent transactions represent a very small percentage of total transactions.

BankGuard is being developed as a complete fraud detection platform rather than only a machine learning model.

The system is designed around the following flow:

```text
Transaction
     ↓
Feature Engineering
     ↓
ML Risk Prediction
     ↓
Risk Scoring
     ↓
FastAPI
     ↓
PostgreSQL
     ↓
Dashboard
     ↓
Alert
     ↓
Investigation
     ↓
MLOps
````

The project is being developed incrementally so that each component can be tested before the next component is introduced.

---

# Project Goals

The main goals of BankGuard are:

* Detect potentially fraudulent transactions.
* Handle highly imbalanced fraud datasets.
* Generate fraud probabilities instead of only binary predictions.
* Convert model probabilities into configurable risk levels.
* Explain model predictions using SHAP.
* Track machine learning experiments using MLflow.
* Expose the fraud model through a FastAPI backend.
* Store transactions and alerts in PostgreSQL.
* Provide a React-based fraud monitoring dashboard.
* Support real-time transaction monitoring.
* Provide an investigation workflow for suspicious transactions.
* Introduce event-driven processing using Kafka.
* Add authentication and security controls.
* Monitor model and data behavior in production.
* Containerize and deploy the complete platform.

---

# Architecture

## Current ML Architecture

The current machine learning pipeline is:

```text
PaySim Dataset
      ↓
Data Inspection
      ↓
Exploratory Data Analysis
      ↓
Preprocessing
      ↓
Feature Engineering Analysis
      ↓
Model Training
      ↓
Model Evaluation
      ↓
Risk Scoring
      ↓
SHAP Explainability
```

---

## Planned Complete Architecture

```text
                 ┌─────────────────────────┐
                 │  Bank Transaction        │
                 │       Simulator          │
                 └────────────┬────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │     FastAPI      │
                    │    Risk Engine   │
                    └────────┬─────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
          Validation    Feature Engine  Authentication
                             │
                             ▼
                    ┌──────────────────┐
                    │   Fraud Model    │
                    │     XGBoost      │
                    └────────┬─────────┘
                             │
                             ▼
                    Fraud Probability
                             │
                             ▼
                       Risk Scoring
                       /          \
                      /            \
                     ▼              ▼
              PostgreSQL       Alert Engine
                     \              /
                      \            /
                       ▼          ▼
                    React Dashboard
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        Monitoring   Investigation   Customer Risk
                           │
                           ▼
                         MLOps
```

---

# Technology Stack

## Machine Learning

* Python
* Pandas
* NumPy
* Scikit-learn
* XGBoost

## Explainable AI

* SHAP

## Backend

* FastAPI

## Frontend

* React
* Tailwind CSS

## Database

* PostgreSQL

## Real-Time Processing

* WebSocket

## Event Streaming

* Kafka

## MLOps

* MLflow

## Containerization

* Docker
* Docker Compose

## CI/CD

* GitHub Actions

## Cloud / Deployment

* AWS

## Development

* Git
* GitHub
* Jupyter Notebook
* VS Code

---

# Project Development Phases

| Phase    | Description                | Status    |
| -------- | -------------------------- | --------- |
| Phase 1  | Project Foundation         | Completed |
| Phase 2  | Fraud ML Pipeline          | Completed |
| Phase 3  | MLflow / MLOps             | Next      |
| Phase 4  | Bank Transaction Simulator | Planned   |
| Phase 5  | FastAPI Risk Engine        | Planned   |
| Phase 6  | PostgreSQL                 | Planned   |
| Phase 7  | React Dashboard            | Planned   |
| Phase 8  | Real-Time Monitoring       | Planned   |
| Phase 9  | Investigation System       | Planned   |
| Phase 10 | Customer Risk Profile      | Planned   |
| Phase 11 | Kafka                      | Planned   |
| Phase 12 | Security                   | Planned   |
| Phase 13 | ML Monitoring              | Planned   |
| Phase 14 | Docker + CI/CD             | Planned   |
| Phase 15 | Deployment                 | Planned   |

---

# Current Progress

## Phase 1 — Project Foundation

**Status: Completed**

The repository structure, development environment, configuration, testing structure, and initial project components have been created.

---

## Phase 2 — Fraud ML Pipeline

**Status: Completed**

Implemented:

* Dataset inspection
* Exploratory Data Analysis
* Data preprocessing
* Feature engineering analysis
* Logistic Regression
* Random Forest
* XGBoost
* Model evaluation
* Fraud probability generation
* Risk scoring design
* SHAP explainability

The project is now ready to introduce MLflow experiment tracking.

---

# Phase 1 — Project Foundation

The initial repository structure is:

```text
BankGuard/
├── backend/
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       ├── core/
│       ├── models/
│       ├── schemas/
│       ├── services/
│       └── utils/
│
├── database/
│
├── docker/
│
├── docs/
│
├── frontend/
│
├── ml/
│
├── simulator/
│
├── tests/
│   ├── __init__.py
│   └── test_health.py
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── pytest.ini
└── README.md
```

---

# Phase 2 — Fraud ML Pipeline

The first major development phase focused on building the fraud detection machine learning pipeline.

The pipeline consists of:

```text
Dataset
   ↓
EDA
   ↓
Preprocessing
   ↓
Feature Engineering
   ↓
Model Training
   ↓
Evaluation
   ↓
Risk Scoring
   ↓
Explainability
```

---

# Dataset

The initial fraud detection model uses the **PaySim** dataset.

Dataset:

```text
PS_20174392719_1491204439457_log.csv
```

Location:

```text
ml/data/raw/
```

Dataset statistics:

```text
Rows:              6,362,620
Original Columns:  11
Fraud Transactions: 8,213
Legitimate:        6,354,407
Fraud Rate:        approximately 0.1291%
```

Target variable:

```text
isFraud
```

Target interpretation:

```text
0 → Legitimate
1 → Fraud
```

Transaction types:

```text
CASH_IN
CASH_OUT
DEBIT
PAYMENT
TRANSFER
```

In the PaySim dataset used by BankGuard, fraud transactions occur in:

```text
CASH_OUT
TRANSFER
```

---

# Exploratory Data Analysis

EDA was performed before model training.

The analysis included:

* Dataset shape
* Data types
* Missing values
* Duplicate records
* Target distribution
* Transaction type distribution
* Transaction amount analysis
* Fraud vs legitimate transactions
* Correlation analysis
* Outlier analysis

Because fraud represents approximately 0.1291% of the dataset, the problem is highly imbalanced.

Therefore, accuracy is not treated as the primary model evaluation metric.

The main evaluation metrics are:

```text
Precision
Recall
F1-score
PR-AUC
ROC-AUC
Confusion Matrix
```

---

# Data Preprocessing

The initial model uses the following features:

```text
step
type
amount
oldbalanceOrg
newbalanceOrig
oldbalanceDest
newbalanceDest
isFlaggedFraud
```

The following identifier fields were excluded from the initial model:

```text
nameOrig
nameDest
```

These fields have very high cardinality and were not directly encoded for the initial model.

---

## Numerical Features

```text
step
amount
oldbalanceOrg
newbalanceOrig
oldbalanceDest
newbalanceDest
isFlaggedFraud
```

Processing:

```text
Median Imputation
       ↓
StandardScaler
```

---

## Categorical Features

```text
type
```

Processing:

```text
Most-Frequent Imputation
       ↓
OneHotEncoder
```

The preprocessing pipeline is implemented using Scikit-learn `ColumnTransformer`.

The preprocessor is fitted only on the training data.

```text
Training Data
     ↓
fit_transform()

Test Data
     ↓
transform()
```

This prevents information from the test set from leaking into preprocessing.

---

## Dataset Split

The dataset was divided using:

```python
train_test_split(
    test_size=0.20,
    random_state=42,
    stratify=y
)
```

Result:

```text
Training Samples: 5,090,096
Testing Samples:  1,272,524
```

Before preprocessing:

```text
X_train: (5,090,096, 8)
X_test:  (1,272,524, 8)
```

After preprocessing:

```text
X_train_processed: (5,090,096, 12)
X_test_processed:  (1,272,524, 12)
```

The increase from 8 to 12 features is caused by one-hot encoding of the five transaction types.

---

# Feature Engineering

Additional fraud-related features were investigated in:

```text
ml/notebooks/03_feature_engineering.ipynb
```

The engineered features include:

```text
balance_change_orig
balance_change_dest
balance_error_orig
balance_error_dest
amount_to_old_balance_ratio
amount_to_new_balance_ratio
amount_to_old_dest_balance_ratio
transaction_hour
transaction_day
```

## Balance Change

```text
balance_change_orig =
oldbalanceOrg - newbalanceOrig
```

```text
balance_change_dest =
newbalanceDest - oldbalanceDest
```

## Balance Consistency

```text
balance_error_orig =
oldbalanceOrg - amount - newbalanceOrig
```

```text
balance_error_dest =
oldbalanceDest + amount - newbalanceDest
```

## Amount Ratios

```text
amount_to_old_balance_ratio =
amount / (oldbalanceOrg + 1)
```

```text
amount_to_new_balance_ratio =
amount / (newbalanceOrig + 1)
```

```text
amount_to_old_dest_balance_ratio =
amount / (oldbalanceDest + 1)
```

## Temporal Features

```text
transaction_hour =
step % 24
```

```text
transaction_day =
step // 24
```

Infinite values were checked and handled during feature engineering.

### Current Feature Engineering Status

The engineered features have been analyzed, but the current trained model was built from the processed dataset generated during the preprocessing stage.

Therefore, the current XGBoost model should not be interpreted as already using all of the engineered features listed above.

Integration of the engineered features into the final reproducible training pipeline is a remaining refinement before production use.

---

# Model Training

Three models were evaluated:

```text
Logistic Regression
Random Forest
XGBoost
```

---

## Logistic Regression

Configuration:

```python
LogisticRegression(
    class_weight="balanced",
    max_iter=1000,
    random_state=42
)
```

---

## Random Forest

Configuration:

```python
RandomForestClassifier(
    n_estimators=100,
    max_depth=12,
    min_samples_leaf=2,
    class_weight="balanced",
    n_jobs=-1,
    random_state=42
)
```

---

## XGBoost

Configuration:

```python
XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=negative_count / positive_count,
    objective="binary:logistic",
    eval_metric="aucpr",
    tree_method="hist",
    n_jobs=-1,
    random_state=42
)
```

The XGBoost configuration uses `scale_pos_weight` to account for the severe class imbalance.

---

# Model Evaluation

The following metrics were used:

* Precision
* Recall
* F1-score
* ROC-AUC
* PR-AUC
* Confusion Matrix

## Initial Results

| Model               | Precision |   Recall | F1-score |  ROC-AUC |   PR-AUC |
| ------------------- | --------: | -------: | -------: | -------: | -------: |
| Logistic Regression |  0.025187 | 0.974437 | 0.049104 | 0.994626 | 0.592328 |
| Random Forest       |  0.093264 | 0.986001 | 0.170410 | 0.999234 | 0.904647 |
| XGBoost             |  0.259107 | 0.995740 | 0.411210 | 0.999832 | 0.961734 |

These values are from the initial evaluation run on the test set.

---

# XGBoost Confusion Matrix

The initial XGBoost confusion matrix was:

```text
[[1266203    4678]
 [      7    1636]]
```

Interpreted as:

```text
True Negative  = 1,266,203
False Positive = 4,678

False Negative = 7
True Positive  = 1,636
```

The confusion matrix is important because it shows how the model's fraud predictions translate into actual false alarms and missed fraud cases.

---

# Evaluation Metrics

## Precision

```text
Precision = TP / (TP + FP)
```

Precision measures how many transactions predicted as fraud were actually fraud.

---

## Recall

```text
Recall = TP / (TP + FN)
```

Recall measures how many actual fraud transactions were detected.

---

## F1-score

```text
F1 = 2 × Precision × Recall
     -------------------------
       Precision + Recall
```

F1 combines precision and recall into a single metric.

---

## ROC-AUC

ROC-AUC measures the model's ability to distinguish between legitimate and fraudulent transactions across classification thresholds.

---

## PR-AUC

PR-AUC summarizes the precision-recall relationship across thresholds.

It is particularly useful for BankGuard because the fraud class is extremely rare.

---

# Risk Scoring

BankGuard is designed to produce a fraud probability rather than only:

```text
Fraud = 1
```

The intended flow is:

```text
XGBoost
   ↓
Fraud Probability
   ↓
Risk Level
   ↓
Decision
```

Example:

```text
Fraud Probability: 0.94
Risk Level: HIGH
Decision: REVIEW
```

---

## Configurable Risk Levels

The current prototype uses:

```text
0.00 – 0.30 → LOW
0.30 – 0.70 → MEDIUM
0.70 – 1.00 → HIGH
```

Example decision mapping:

```text
LOW     → ALLOW
MEDIUM  → REVIEW
HIGH    → REVIEW
```

These thresholds are configurable project-level thresholds and are not intended to represent universal banking policy.

---

# SHAP Explainability

BankGuard uses SHAP to make model predictions more interpretable.

The intended workflow is:

```text
Transaction
     ↓
XGBoost
     ↓
Fraud Probability
     ↓
SHAP
     ↓
Feature Contributions
     ↓
Explanation
```

SHAP is used to investigate which model features contributed to predictions.

The analysis includes:

* SHAP TreeExplainer
* Global feature importance
* SHAP summary plots
* SHAP feature-importance bar plots

Because the test dataset contains more than 1.2 million transactions, a smaller sample is used for SHAP analysis.

Current sample:

```text
2,000 test transactions
```

---

# ML Artifacts

The project generates several machine learning artifacts.

```text
ml/artifacts/
├── models/
│   └── fraud_xgboost.pkl
│
├── preprocessors/
│   └── preprocessor.pkl
│
└── reports/
```

The preprocessing artifact stores the fitted transformation pipeline.

The model artifact stores the trained machine learning model.

Large generated artifacts are excluded from GitHub using `.gitignore`.

---

# Project Structure

```text
BankGuard/
│
├── backend/
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       ├── core/
│       ├── models/
│       ├── schemas/
│       ├── services/
│       └── utils/
│
├── database/
│
├── docker/
│
├── docs/
│
├── frontend/
│
├── ml/
│   ├── data/
│   │   ├── raw/
│   │   └── processed/
│   │
│   ├── artifacts/
│   │   ├── models/
│   │   ├── preprocessors/
│   │   └── reports/
│   │
│   ├── notebooks/
│   │   ├── 01_eda.ipynb
│   │   ├── 02_preprocessing.ipynb
│   │   ├── 03_feature_engineering.ipynb
│   │   ├── 04_model_training.ipynb
│   │   └── 05_shap_analysis.ipynb
│   │
│   └── configs/
│
├── simulator/
│
├── tests/
│   ├── __init__.py
│   └── test_health.py
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── pytest.ini
└── README.md
```

---

# Phase 3 — MLflow

**Status: Next**

The next phase introduces MLflow into the machine learning workflow.

The goal is to make model experiments reproducible and trackable.

The planned workflow is:

```text
Experiment
     ↓
Model Training
     ↓
MLflow Tracking
     ↓
Model Evaluation
     ↓
Model Artifact
     ↓
Model Version
     ↓
Production Model
```

MLflow will track:

```text
Model Type
Hyperparameters
Precision
Recall
F1-score
PR-AUC
ROC-AUC
Training Dataset Information
Model Artifact
```

The planned model management structure is:

```text
fraud-model
 ├── v1
 ├── v2
 └── production
```

---

# Phase 4 — Bank Transaction Simulator

After MLflow, BankGuard will introduce a simulated bank transaction gateway.

The simulator will generate transaction events for testing the complete system.

Example transaction:

```json
{
  "transaction_id": "TX98231",
  "customer_id": "C1029",
  "amount": 85000,
  "merchant_category": "ELECTRONICS",
  "device_id": "D882",
  "location": "Mumbai",
  "timestamp": "2026-09-29T14:32:21",
  "payment_method": "CARD"
}
```

The simulator will be used to generate both normal and suspicious transaction scenarios.

---

# Phase 5 — FastAPI Risk Engine

The trained fraud model will eventually be exposed through FastAPI.

Planned architecture:

```text
Transaction
     ↓
FastAPI
     ↓
Validation
     ↓
Feature Engineering
     ↓
Preprocessor
     ↓
Fraud Model
     ↓
Risk Score
```

Planned endpoint:

```http
POST /api/v1/risk/score
```

Example request:

```json
{
  "transaction_id": "TX98231",
  "customer_id": "C1029",
  "amount": 85000
}
```

Example response:

```json
{
  "transaction_id": "TX98231",
  "fraud_probability": 0.94,
  "risk_level": "HIGH",
  "decision": "REVIEW"
}
```

Additional planned endpoints include:

```text
POST  /api/v1/transactions
GET   /api/v1/transactions
GET   /api/v1/transactions/{id}

GET   /api/v1/alerts
PATCH /api/v1/alerts/{id}

GET   /api/v1/dashboard/stats

GET   /api/v1/customers/{id}
```

---

# Phase 6 — PostgreSQL

The planned database will contain entities such as:

## Customers

```text
id
customer_id
account_age
created_at
status
```

## Transactions

```text
id
transaction_id
customer_id
amount
merchant_category
device_id
location
timestamp
fraud_probability
risk_level
decision
created_at
```

## Alerts

```text
id
transaction_id
risk_score
reason
status
created_at
```

## Investigations

```text
id
transaction_id
analyst
status
notes
resolution
created_at
updated_at
```

---

# Phase 7 — React Dashboard

The React dashboard will provide the user interface for BankGuard.

Planned dashboard sections include:

```text
Login
Dashboard
Transactions
Alerts
Investigations
Customers
Model Monitoring
```

Dashboard metrics:

```text
Total Transactions
Fraud Detected
High Risk
Under Investigation
Fraud Rate
```

Planned visualizations:

```text
Transaction Volume
Fraud Trend
Risk Distribution
Fraud by Category
Fraud by Location
```

---

# Phase 8 — Real-Time Monitoring

BankGuard will eventually support real-time transaction monitoring.

Planned flow:

```text
Transaction Simulator
        ↓
      FastAPI
        ↓
      ML Model
        ↓
    PostgreSQL
        ↓
     WebSocket
        ↓
 React Dashboard
```

The dashboard should update when new transactions arrive without requiring a manual page refresh.

---

# Phase 9 — Investigation System

Suspicious transactions will be available for investigation.

Example:

```text
Transaction Details

Transaction: TX98231
Amount: ₹85,000
Customer: C1029

Fraud Probability: 94%
Risk Level: HIGH

Risk Signals:
- Unusual transaction amount
- New device
- Unusual transaction time
- High transaction frequency
```

Investigation workflow:

```text
Pending
   ↓
Under Investigation
   ↓
Confirmed Fraud / Legitimate
```

---

# Phase 10 — Customer Risk Profile

BankGuard will eventually provide customer-level risk information.

Example:

```text
Customer: C1029

Risk Score: 82/100

Transactions: 1,284
High-Risk Transactions: 7
Devices Used: 5
Locations: 3
```

Transaction history can then be displayed as:

```text
₹1,200    LOW
₹2,100    LOW
₹85,000   HIGH
₹72,000   HIGH
```

---

# Phase 11 — Kafka

Kafka will be introduced after the REST and WebSocket architecture is functional.

Planned event-driven architecture:

```text
Simulated Bank
      ↓
    Kafka
      ↓
Fraud Consumer
      ↓
Feature Service
      ↓
ML Model
      ↓
PostgreSQL
      ↓
Alert Service
```

Kafka will provide an event-driven architecture for transaction processing.

---

# Phase 12 — Security

Because BankGuard is a banking-oriented application, security will be added as the system develops.

Planned security controls include:

```text
JWT Authentication
Password Hashing
Role-Based Access Control
Input Validation
Rate Limiting
CORS
Environment Variables
API Authentication
Audit Logs
```

Planned roles:

```text
ADMIN
FRAUD_ANALYST
VIEWER
```

Example:

```text
Fraud Analyst
    ↓
View Transactions
Investigate Alerts
Update Investigation

Viewer
    ↓
View Dashboard
```

---

# Phase 13 — MLOps and Monitoring

The final MLOps stage will monitor both model performance and production data behavior.

Planned monitoring information:

```text
MODEL MONITORING

Model: fraud-xgb-vX

Precision
Recall
F1
PR-AUC
ROC-AUC

Data Drift
Prediction Drift

Model Version
```

An important distinction:

```text
Model Performance
        ↓
Uses labeled evaluation data

Data / Prediction Drift
        ↓
Observes changes in production distributions
```

---

# Phase 14 — Docker and CI/CD

The final system will be containerized.

Planned containers include:

```text
React
FastAPI
PostgreSQL
MLflow
Kafka
```

Docker Compose will be used to manage the local multi-service environment.

The CI/CD pipeline will follow:

```text
Git Push
   ↓
Tests
   ↓
Lint
   ↓
Build
   ↓
Docker Image
   ↓
Deployment
```

GitHub Actions will be used for automation.

---

# Phase 15 — Deployment

The final platform is planned for deployment using AWS infrastructure.

The deployment architecture will be determined after the local system, Docker environment, CI/CD pipeline, and monitoring components are completed.

---

# Installation

Clone the repository:

```bash
git clone <repository-url>
cd BankGuard
```

Create a Python virtual environment:

### Windows

```cmd
python -m venv .venv
```

Activate:

```cmd
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

# Environment Setup

Install the required Python dependencies:

```bash
pip install -r requirements.txt
```

Create an environment file:

```text
.env
```

Use `.env.example` as the template.

Do not commit `.env` to GitHub.

---

# Running the ML Notebooks

The ML pipeline notebooks are located in:

```text
ml/notebooks/
```

Run them in the following order:

```text
01_eda.ipynb
      ↓
02_preprocessing.ipynb
      ↓
03_feature_engineering.ipynb
      ↓
04_model_training.ipynb
      ↓
05_shap_analysis.ipynb
```

Each stage should be completed and verified before proceeding to the next stage.

---

# Git and Data Policy

Large datasets and generated ML artifacts are intentionally excluded from GitHub.

The following are ignored:

```text
ml/data/raw/
ml/data/processed/
ml/artifacts/models/
ml/artifacts/preprocessors/
ml/artifacts/reports/
```

This prevents large files such as the PaySim CSV and generated model artifacts from being committed to the repository.

The repository contains the code and notebooks required to reproduce the ML workflow.

---

# Reproducibility

The project uses fixed random seeds where applicable.

Examples include:

```python
random_state=42
```

The preprocessing pipeline is saved separately from the model.

This allows the future inference system to use:

```text
Raw Transaction
      ↓
Same Preprocessor
      ↓
Same Feature Representation
      ↓
Trained Model
      ↓
Prediction
```

MLflow will further improve reproducibility by tracking model parameters, metrics, datasets, and model artifacts.

---

# Development Roadmap

The development roadmap is:

```text
M1
Project Foundation
    ↓
M2
Fraud ML Model
    ↓
M3
MLflow
    ↓
M4
Transaction Simulator
    ↓
M5
FastAPI Risk Engine
    ↓
M6
PostgreSQL
    ↓
M7
React Dashboard
    ↓
M8
Real-Time Monitoring
    ↓
M9
Investigation System
    ↓
M10
Customer Risk Profile
    ↓
M11
Kafka
    ↓
M12
Security
    ↓
M13
MLOps / Monitoring
    ↓
M14
Docker + CI/CD
    ↓
M15
Deployment
```

---

# Current Status

```text
┌───────────────────────────────────────────┐
│              BANKGUARD STATUS             │
├───────────────────────────────────────────┤
│ Phase 1 — Foundation             COMPLETE │
│ Phase 2 — Fraud ML Pipeline      COMPLETE │
│ Phase 3 — MLflow                 COMPLETE    │
│ Phase 4 — Transaction Simulator   COMPLETE  │
│ Phase 5 — FastAPI                PLANNED  │
│ Phase 6 — PostgreSQL              PLANNED  │
│ Phase 7 — React Dashboard         PLANNED  │
│ Phase 8 — Real-Time Monitoring    PLANNED  │
│ Phase 9 — Investigation           PLANNED  │
│ Phase 10 — Customer Risk          PLANNED  │
│ Phase 11 — Kafka                  PLANNED  │
│ Phase 12 — Security              PLANNED  │
│ Phase 13 — MLOps Monitoring      PLANNED  │
│ Phase 14 — Docker + CI/CD        PLANNED  │
│ Phase 15 — Deployment            PLANNED  │
└───────────────────────────────────────────┘
```

---

# Project Objective

BankGuard aims to evolve from a fraud classification model into a complete transaction risk management and fraud investigation platform.

The final system will combine:

```text
Machine Learning
       +
Explainable AI
       +
FastAPI
       +
PostgreSQL
       +
React
       +
WebSocket
       +
Kafka
       +
MLflow
       +
Docker
       +
CI/CD
       +
AWS
```

The final objective is to provide an end-to-end architecture capable of:

```text
Transaction
     ↓
Detection
     ↓
Risk Scoring
     ↓
Explanation
     ↓
Alert
     ↓
Investigation
     ↓
Monitoring
     ↓
Model Lifecycle Management
```

---

## Development Principle

BankGuard is being developed incrementally.

The project does not attempt to implement all components simultaneously.

The immediate sequence is:

```text
Phase 1
Foundation
   ↓
Phase 2
Fraud ML Pipeline
   ↓
Phase 3
MLflow
   ↓
Phase 4
Transaction Simulator
   ↓
Phase 5
FastAPI
```

Each phase is tested and verified before moving to the next phase.

````

