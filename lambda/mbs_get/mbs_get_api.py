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
import os, sys
import backoff
from gremlin_python import statics
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.driver.protocol import GremlinServerError
from gremlin_python.driver import serializer
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __
from gremlin_python.process.strategies import *
from gremlin_python.process.traversal import T
from aiohttp.client_exceptions import ClientConnectorError
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import ReadOnlyCredentials
from types import SimpleNamespace
import json
import logging

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


reconnectable_err_msgs = [ 
    'ReadOnlyViolationException',
    'Server disconnected',
    'Connection refused',
    'Connection was already closed',
    'Connection was closed by server',
    'Failed to connect to server: HTTP Error code 403 - Forbidden'
]

retriable_err_msgs = ['ConcurrentModificationException'] + reconnectable_err_msgs

network_errors = [OSError, ClientConnectorError]

retriable_errors = [GremlinServerError, RuntimeError, Exception] + network_errors

CLUSTER_ENDPOINT = os.environ['CLUSTER_ENDPOINT']
CLUSTER_PORT = os.environ['CLUSTER_PORT']
HTTP_SUCCESS = 200
HTTP_INTERNAL_ERROR = 500


if CLUSTER_ENDPOINT is None or CLUSTER_PORT is None:
    raise ValueError('init_environment_variables, environment variables were not loaded')


def prepare_iamdb_request(database_url):
        
    service = 'neptune-db'
    method = 'GET'

    access_key = os.environ['AWS_ACCESS_KEY_ID']
    secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
    region = os.environ['AWS_REGION']
    session_token = os.environ['AWS_SESSION_TOKEN']
    
    creds = SimpleNamespace(
        access_key=access_key, secret_key=secret_key, token=session_token, region=region,
    )

    request = AWSRequest(method=method, url=database_url, data=None)
    SigV4Auth(creds, service, region).add_auth(request)
    return (database_url, request.headers.items())
        
def is_retriable_error(e):

    is_retriable = False
    err_msg = str(e)
    
    if isinstance(e, tuple(network_errors)):
        is_retriable = True
    else:
        is_retriable = any(retriable_err_msg in err_msg for retriable_err_msg in retriable_err_msgs)
    
    logger.error('error: [{}] {}'.format(type(e), err_msg))
    logger.info('is_retriable: {}'.format(is_retriable))
    
    return is_retriable

def is_non_retriable_error(e):      
    return not is_retriable_error(e)
        
def reset_connection_if_connection_issue(params):
    
    is_reconnectable = False

    e = sys.exc_info()[1]
    err_msg = str(e)
    
    if isinstance(e, tuple(network_errors)):
        is_reconnectable = True
    else:
        is_reconnectable = any(reconnectable_err_msg in err_msg for reconnectable_err_msg in reconnectable_err_msgs)
        
    logger.info('is_reconnectable: {}'.format(is_reconnectable))
        
    if is_reconnectable:
        global conn
        global g
        conn.close()
        conn = create_remote_connection()
        g = create_graph_traversal_source(conn)
     
@backoff.on_exception(backoff.constant,
    tuple(retriable_errors),
    max_tries=5,
    jitter=None,
    giveup=is_non_retriable_error,
    on_backoff=reset_connection_if_connection_issue,
    interval=1)
    
def create_graph_traversal_source(conn):
    return traversal().withRemote(conn)
    
def create_remote_connection():
    logger.info('Creating remote connection')
    
    (database_url, headers) = connection_info()

    return DriverRemoteConnection(
        database_url,
        'g',
        pool_size=1,
        message_serializer=serializer.GraphSONSerializersV2d0(),
        headers=headers
        )
    
def connection_info():
    
    database_url = 'wss://{}:{}/gremlin'.format(CLUSTER_ENDPOINT, CLUSTER_PORT)
    
    if 'USE_IAM' in os.environ and os.environ['USE_IAM'] == 'true':
        return prepare_iamdb_request(database_url)
    else:
        return (database_url, {})
    
conn = create_remote_connection()
g = create_graph_traversal_source(conn)

    
def whole(v):
    try:
        return float(v)
    except ValueError:
        return v
        
        
def transform(items):
    resp = []
    for item in items:
        loan = {}
        for k,v in item.items():
            loan[k] = whole(v)
        resp.append(loan)
    return resp            
    
def invalid_request_response():
    return{
        'statusCode': HTTP_SUCCESS,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': 'Invalid request type'
    }
        
    
def get_all_loans_by_cusip(id):
   request=g.V(id).outE().inV().valueMap().by(__.unfold()).toList()
   return transform(request)
    
def get_all_loans_by_seller(id):
    request=g.V().hasLabel('seller').has('id',id).outE().inV().valueMap().by(__.unfold()).toList()
    return transform(request)      
        
def get_all_loans_by_servicer(id):
   request=g.V().hasLabel('servicer').has('id',id).outE().inV().valueMap().by(__.unfold()).toList()
   return transform(request)    
        

def get_all_vertices():
    request=g.V().__.fold()
    return transform(request)   
    

def lambda_handler(event, context):
    request = event.get('body', None)
    logger.info(f'request: {json.dumps(request)}')
   
    if request is None:
        invalid_request_response()
      
    body = json.loads(request)

    param = body['queryStringParameters']['param']
    id = body['queryStringParameters']['id']
    
    if(str(param) == "loansbycusip"):
        response = get_all_loans_by_cusip(id)
    elif(str(param) == "loansbyseller"):
        response = get_all_loans_by_seller(id)
    elif(str(param) == "loansbyservicer"):
        response = get_all_loans_by_servicer(id)
    elif(str(param) == "getallvertices"):
        response = get_all_vertices()
    else:
        invalid_request_response()
    
    logger.info(f'response: {response}')
   
    return{
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(response)
    }
