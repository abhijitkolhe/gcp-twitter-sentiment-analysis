#!/usr/bin/env python3

# Dataflow job (not templatable) for Twitter sentiment inference

import argparse
import json
import logging
import sys

import apache_beam as beam
import preprocessor as p
import tensorflow as tf

from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.options.pipeline_options import SetupOptions
from apache_beam.options.pipeline_options import StandardOptions

INPUT_ID_KEY = 'id'
INPUT_TEXT_KEY = 'text'
RESULT_KEY = 'prob'

# BigQuery table has id(int), prob(float) columns
BIGQUERY_SCHEMA = f'{INPUT_ID_KEY}:INTEGER,{RESULT_KEY}:FLOAT'

class Predict(beam.DoFn):
    def __init__(self, model_dir):
        beam.DoFn.__init__(self)
        self.model_dir = model_dir
        self.graph = None
        self.sess = None
        self.input_tensor = None
        self.output_tensor = None

    def process(self, msg):
        # inputs: PubsubMessage
        if not self.sess:
            logging.info('Loading Tensorflow saved model...')
            self.graph = tf.compat.v1.get_default_graph()
            with self.graph.as_default():
                self.sess = tf.compat.v1.Session(graph=self.graph)
                metagraph_def = tf.compat.v1.saved_model.load(self.sess,
                        [tf.saved_model.SERVING], self.model_dir)
                
            logging.info('Successfully loaded.')
            signature_def = metagraph_def.signature_def[tf.saved_model.DEFAULT_SERVING_SIGNATURE_DEF_KEY]

            # retrieve input / output tensor using signature_def
            for sig_input in signature_def.inputs.values():
                self.input_tensor = self.graph.get_tensor_by_name(sig_input.name)
                break

            for sig_output in signature_def.outputs.values():
                self.output_tensor = self.graph.get_tensor_by_name(sig_output.name)
                break

        logging.info('Preprocessing...')
        # preprocess text using tweet-preprocessor
        preprocessed = p.clean(msg.data.decode('utf-8'))
        logging.info(preprocessed)

        feed_dict = {
            self.input_tensor: [[preprocessed]]
        }
        try:
            result = self.sess.run(self.output_tensor, feed_dict)
        except tf.python.framework.errors_impl.InvalidArgumentError:
            # if text contains invalid character(/, :, ...), the error occurs
            # in that case, we just predict as neutral
            logging.info('Cannot parse the input text. The result will be 0.5.')
            result = [[0.5]]

        logging.info('Output has been created...')

        yield {
            INPUT_ID_KEY: msg.attributes[INPUT_ID_KEY],
            RESULT_KEY: float(result[0][0])
        }

class UserOptions(PipelineOptions):
    @classmethod
    def _add_argparse_args(cls, parser):
        # pre-trained Tensorflow model directory
        parser.add_argument(
            '--model_dir',
            required=True,
            help='Tensorflow model directory. This can be Google Cloud Storage path.')
        
        # PubSub topic for data ingestion
        parser.add_argument(
            '--input_topic',
            required=True,
            help='Input PubSub topic name')

        # BigQuery table for output(probability)
        parser.add_argument(
            '--output_bigquery_table',
            required=True,
            help='Output BigQuery table name')

def predict(model_dir, project, input_topic, output_bigquery_table, beam_options=None):
    with beam.Pipeline(options=beam_options) as p:
        _ = (p
        | 'Input' >> beam.io.ReadFromPubSub(topic=f'projects/{project}/topics/{input_topic}', with_attributes=True)
        | 'Predict' >> beam.ParDo(Predict(model_dir))
        | 'Write predictions' >> beam.io.WriteToBigQuery(output_bigquery_table,
                                    project=project,
                                    schema=BIGQUERY_SCHEMA,
                                    write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND))

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    parser = argparse.ArgumentParser()
    known_args, pipeline_args = parser.parse_known_args(None)

    beam_options = PipelineOptions(pipeline_args)
    # beam_options.view_as(SetupOptions).save_main_session = True
    # use streaming option 
    beam_options.view_as(StandardOptions).streaming = True
    user_options = beam_options.view_as(UserOptions)
    cloud_options = beam_options.view_as(GoogleCloudOptions)

    # input PubSub topic -> current Dataflow -> output BigQuery table
    predict(user_options.model_dir, cloud_options.project, user_options.input_topic,
            user_options.output_bigquery_table, beam_options)