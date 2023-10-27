# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import json
import boto3
import os
import logging
import psycopg2

logger = logging.getLogger()
logger.setLevel(logging.INFO)

secret_arn = os.environ.get('RDS_SECRET')
db_name = os.environ.get('RDS_DBNAME')
bucket_name = os.environ.get('BUCKET_NAME')

try:
    secret_client = boto3.client('secretsmanager')
    secret_value = secret_client.get_secret_value(SecretId=secret_arn)
except Exception as e:
    logger.error("Error: Could not get secret")
    logger.error(str(e))


def handler(event, context):
    logger.info(f'request: {json.dumps(event)}')
    
    obj = boto3.client('s3')
    ddl_queries = obj.list_objects_v2(Bucket=bucket_name, Prefix='ddl')
    dml_queries = obj.list_objects_v2(Bucket=bucket_name, Prefix='dml')

    try:
        secret_dict = json.loads(secret_value['SecretString'])
        username = secret_dict['username']
        password = secret_dict['password']
        host = secret_dict['host']
        port = secret_dict['port']
        dbname = secret_dict['engine']
        conn = psycopg2.connect(database=dbname, user=username, password=password, host=host, port=port)
        logger.info('Connected to Database successfully')
        cur = conn.cursor()
        for query in ddl_queries['Contents']:
            sql = obj.get_object(Bucket=bucket_name, Key=query['Key'])['Body'].read().decode()
            logger.info(sql)
            cur.execute(sql)
        
        for query in dml_queries['Contents']:
            sql = obj.get_object(Bucket=bucket_name, Key=query['Key'])['Body'].read().decode()
            logger.info(sql)
            cur.execute(sql)
        conn.commit()
    except Exception as e:
        logger.error(f'Failed loading the sample source dataset: {str(e)}')
    finally:
        logger.info("cleanup of cursor and db connection")
        cur.close()
        conn.close()
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/plain'
        },
        'body': 'Sample source dataset loaded successfully \n'
    }
