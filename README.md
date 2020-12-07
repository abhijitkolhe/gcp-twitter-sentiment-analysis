# GCP Twitter Sentiment Analysis
This repository contains various codes in GCP which implement Twitter sentiment analysis pipeline.

# Architecture
![architecture](https://user-images.githubusercontent.com/17065620/101309089-d5e50680-388e-11eb-80c6-006de9e9b64c.png)

# What is it for?
This project aims to mimic data ingestion and create inference pipeline using whth GCP (Google Cloud Platform).

The project contains 3 modules which are...
- Training sentiment analysis model using Tensorflow
- Cloud Functions that calls Twitter Recent API
- Cloud Dataflow that predicts polarity based on ingested text data

# Prerequisites
This project is tested on Python 3.8.5 (Training, Local Dataflow Run), Go 1.13 (Cloud Functions).

Other environments should be tested later.

# Training Model
You can train your own model using [train.ipynb](train-model/train.ipynb) file.

This requires tensorflow 2.3.1, tweet-preprocessor 0.6.0, pandas 1.1.4. The installation script is included in the Notebook file.

The output model will be created in train-model/model/ directory as Tensorflow SavedModel format. The Dataflow pipeline retrieves model data from Cloud Storage so you should store the model in the Storage.

You can easily create a bucket and upload your model directory to the bucket as follows.
```
## you may need to authenticate to GCP
# gcloud auth login
## create a bucket "some-bucket"
gsutil mb -c standard gs://some-bucket
## copy directory "train-model/model/" to the bucket
gsutil cp -R train-model/model/ gs://some-bucket
```

# Add Cloud Scheduler (+ Pub/Sub Topic)
You can create a cronjob using Cloud Scheduler. Cloud Scheduler publishes to Pub/Sub topic and Cloud Functions will subscribe that topic.

You can create Pub/Sub topic and Cloud Scheduler using gcloud tool.
```
# create a topic named "cron-topic"
gcloud pubsub topics create cron-topic
# create a scheduler named "cron-pubsub-trigger" which publishes to the topic "cron-topic" every minute.
gcloud scheduler jobs create pubsub cron-pubsub-trigger --schedule="* * * * *" --topic=cron-topic
```
