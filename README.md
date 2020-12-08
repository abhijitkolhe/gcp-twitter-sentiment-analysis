# GCP Twitter Sentiment Analysis
Create Twitter sentiment Inference pipeline from scratch using Google Cloud Platform.

## Architecture
![architecture](https://user-images.githubusercontent.com/17065620/101309089-d5e50680-388e-11eb-80c6-006de9e9b64c.png)

## What is it for?
This project aims to mimic data ingestion and create inference pipeline using whth GCP (Google Cloud Platform).

The project contains 3 modules.
- Training sentiment analysis model using Tensorflow
- Cloud Functions that calls Twitter Recent API
- Cloud Dataflow that predicts polarity based on ingested text data

## Prerequisites
This project is tested on Python 3.8.5 (Training, Local Dataflow Run), Go 1.13 (Cloud Functions).

Other environments should be tested later.

## Training Model
You can train your own model using [train/train.ipynb](train-model/train.ipynb) file.

This requires tensorflow 2.3.1, tweet-preprocessor 0.6.0, pandas 1.1.4. The installation script is included in the Notebook file.

The output model will be created in train-model/model/ directory as Tensorflow SavedModel format. The Dataflow pipeline retrieves model data from Cloud Storage so you should store the model in the Storage.

You can easily create a bucket and upload your model directory to the bucket as follows.
```
# you may need to authenticate to GCP
gcloud auth login
# create a bucket "some-bucket"
gsutil mb -c standard gs://some-bucket
# copy directory "train-model/model/" to the bucket
gsutil cp -R train-model/model/ gs://some-bucket
# check the directory has been uploaded to Cloud Storage
gsutil ls gs://some-bucket/train/model
```

## Add Cloud Scheduler (+ Pub/Sub Topic)
You can create a cronjob using Cloud Scheduler. Cloud Scheduler publishes to Pub/Sub topic and Cloud Functions will subscribe that topic.

You can create Pub/Sub topic and Cloud Scheduler using gcloud tool.
```
# create a topic named "cron-topic"
gcloud pubsub topics create cron-topic
# create a scheduler named "cron-pubsub-trigger" which publishes to the topic "cron-topic" every minute.
gcloud scheduler jobs create pubsub cron-pubsub-trigger --schedule="* * * * *" --topic=cron-topic
# check the scheduler has been created
gcloud scheduler jobs list
```

## Add Cloud Functions (+ Pub/Sub Topic)
[cloud-functions/functions.go](cloud-functions/function.go) calls Twitter Recent API and retrieves data for a minute (from 2 minutes ago ~ 1 minute ago). The query set in the function is "corona" and the number of maximum result is "10". You can modify "searchingQuery" and "maxResults" variables to change the behavior. You can also add environment variables to dynamically change those settings.

There are several environment variables you should set in this function.

- BEARER_TOKEN
  - First of all, you should apply for the developer API access in [Twitter Developer API](https://developer.twitter.com/en/apply-for-access). Also check [Bearer Tokens](https://developer.twitter.com/en/docs/authentication/oauth-2-0/bearer-tokens) to get Bearer token to access the API.

- GCP_PROJECT
  - This environment variable is your GCP project name.
  
- TOPIC_ID
  - The topic ID of Pub/Sub which Twitter data will be sent to. You should create your Pub/Sub topic before the function call.
  
You can create Cloud Functions as follows.
```
# create a topic named "twitter-data-topic" which the data will be sent to
gcloud pubsub topics create twitter-data-topic
# create a function named "twitter-data-ingestion"
gcloud functions deploy twitter-data-ingestion --source=cloud-functions/functions.go --runtime=go113
# you may check the function has been created
gcloud functions list
```

## Run Dataflow Pipeline
You could run a Dataflow pipeline in your local machine or in GCP.
Before running the pipeline, you should create BigQuery table. The table contains integer column "id" (Twitter post ID) and "prob" (probability of being positive).

A BigQuery table can be created using bq command line tool.
```
# create dataset "twitter_data_set" in project "myproject"
bq mk -d \
  --description "Twitter data" \
  myproject:twitter_data_set
  
# create table "output" in "twitter_data_set" in project "myproject" 
bq mk --table \
  --description "Output table" \
  myproject:twitter_data_set.output \
  id:INTEGER,prob:FLOAT
```

Dataflow pipeline needs some arguments.
- --model_dir
  - Model directory. This can be Cloud Storage path (gs://).
  - ex) gs://some-bucket/train/model
  
- --input_topic
  - Input Pub/Sub topic name published by Cloud Functions we've made.
  - ex) twitter-data-topic
  
- --output_bigquery_table
  - BigQuery table name.
  - ex) myproject:twitter_data_set.output
  
- --project
  - GCP project name.
  - ex) myproject
  
You can run Dataflow locally as follows. Note that Python 3.8.5 (or 3.8.x) should be installed in your machine.
```
# install Python libraries
pip install apache-beam[gcp]==2.25.0 \
  tensorflow==2.3.1 \
  tweet-preprocessor==0.6.0 
# run Dataflow locally
python dataflow/predict.py \
  --project myproject \
  --model_dir gs://some-bucket/train/model --input_topic twitter-data-topic \
  --output_bigquery_table myproject:twitter_data_set.output
```

Also Dataflow pipeline can be run in the cloud.
```
# create Dataflow job in GCP (using region asia-northeast1; you can modify --region argument to change the region)
python dataflow/predict.py --runner DataflowRunner \
  --project myproject \
  --model_dir gs://some-bucket/train/model --input_topic twitter-data-topic \
  --output_bigquery_table myproject:twitter_data_set.output \
  --region asia-northeast1 \
  --setup_file dataflow/setup.py
```

## Run a whole pipeline
Just run your scheduler to start streaming.
```
# run Cloud Scheduler named "cron-pubsub-trigger"
gcloud scheduler jobs run cron-pubsub-trigger
```

## Caveats
- Due to the Cloud Functions is called on-demand, the Pub/Sub client will be created at the time it is triggered. This causes the model is loaded every time the function is called. If you are using a server and the client instance is to be made once, it may not be a problem.

## License
[MIT](https://choosealicense.com/licenses/mit/)
