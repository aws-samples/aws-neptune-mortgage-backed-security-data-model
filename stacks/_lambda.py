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

import aws_cdk as cdk

import os
from aws_cdk import (
    Stack,
    # Duration,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_s3 as _s3,
    RemovalPolicy,
    aws_s3_deployment as s3_deployment,
    aws_ec2 as ec2,
    Duration,
    aws_iam as iam,
)

from constructs import Construct

class LambdaStack(Stack):


    def __init__(self, scope: Construct, id: str, vpc, rds_secret, rds_database_name, neptune_endpoint, neptune_endpoint_role, neptune_arn, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Defines an S3 resource to upload SQL scripts
        sqlscripts_s3 = _s3.Bucket(
            self, 'mbs-sqlscripts-bucket',
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Defines an S3 deployment to upload SQL scripts
        sqlscripts_s3_files = s3_deployment.BucketDeployment(self,
                                    'UploadSqlScripts',
                                    sources=[s3_deployment.Source.asset('sqlscripts')],
                                    destination_bucket=sqlscripts_s3)

        # Define parameters for layer build
        _runtime = _lambda.Runtime.PYTHON_3_9
        _code_path = os.path.dirname(os.path.realpath(__file__))

        _pip_output_folder = f'/asset-output/python/lib/{_runtime.to_string()}/site-packages'
        _pip_command = f'pip install -r requirements.txt -t {_pip_output_folder}'
        _bundling_command = ['bash', '-c', _pip_command]

        layer_bundling = cdk.BundlingOptions(image=_runtime.bundling_image, command=_bundling_command)

        # Define parameters specific to pyscopg2 / postgres layer build
        layer_code_postgres = cdk.aws_lambda.Code.from_asset(os.path.join(_code_path,'../layers/postgres'), bundling=layer_bundling)
        layer_postgres = cdk.aws_lambda.LayerVersion(
            self, 'PostgresLayer',
            compatible_runtimes=[_runtime],
            code=layer_code_postgres,
        )

        # Define parameters specific to gremlin layer build
        layer_code_gremlin = cdk.aws_lambda.Code.from_asset(os.path.join(_code_path,'../layers/gremlin'), bundling=layer_bundling)
        layer_gremlin = cdk.aws_lambda.LayerVersion(
            self, 'GremlinLayer',
            compatible_runtimes=[_runtime],
            code=layer_code_gremlin,
        )
            

        # Defines an AWS Lambda resource - DB loader Lambda
        dbloader_lambda = _lambda.Function(
            self, 'DBLoaderHandler',
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset(os.path.join(_code_path,'../lambda/dbloader')),
            handler='dbloader.handler',
            layers=[layer_postgres],
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                'BUCKET_NAME': sqlscripts_s3.bucket_name,
                'RDS_SECRET': rds_secret.secret_arn,
                'RDS_DBNAME': str(rds_database_name)
            }
        )

        # Defines an AWS Lambda resource - MBS Get API Lambda
        mbs_get_lambda = _lambda.Function(
            self, 'MBSGetHandler',
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset(os.path.join(_code_path,'../lambda/mbs_get')),
            timeout=Duration.seconds(10),
            handler='mbs_get_api.lambda_handler',
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            layers=[layer_gremlin],
            environment={
                'CLUSTER_ENDPOINT': neptune_endpoint,
                'CLUSTER_PORT': '8182',
                'USE_IAM': 'true',
                'LOG_LEVEL': 'INFO'
            }
        )

        #Grant S3 read access to dbloader lambda
        sqlscripts_s3.grant_read(dbloader_lambda)

        #Grant Secret manager read access to dbloader lambda
        rds_secret.grant_read(dbloader_lambda)

        
        #Define MbsApi Api Gateway resource
        mbsapi = apigw.RestApi(self, "Api",
                      rest_api_name="MbsApi")
        
        #Add resource path for dbloader lambda
        dbloader = mbsapi.root.add_resource("dbloader")
        dbloader.add_method("POST", apigw.LambdaIntegration(
            handler=dbloader_lambda
        ),
        api_key_required=True)

        #Add resource path for Mbs get api lambda
        mbsget = mbsapi.root.add_resource("mbsget")
        mbsget.add_method("POST", apigw.LambdaIntegration(
            handler=mbs_get_lambda,
            request_parameters={
                'integration.request.querystring.param': 'method.request.querystring.param',
                'integration.request.querystring.id': 'method.request.querystring.id'
            }
            ),
            request_parameters={
                'method.request.querystring.param': True,
                'method.request.querystring.id': True
            },
            api_key_required=True
        )

        #Create API key for Mbs API
        mbs_api_key = mbsapi.add_api_key(
            'MbsApiKey',
            description='MbsApiKey',
        )

        #Create usage plan for Mbs API
        mbs_api_usage_plan = mbsapi.add_usage_plan(
            'MbsApiUsagePlan',
            name='MbsApiUsagePlan',
            description='MbsApiUsagePlan',
            )
        
        #Add the API key to the usage plan
        mbs_api_usage_plan_key = mbs_api_usage_plan.add_api_key(mbs_api_key)
        
        #Associate usage plan with API stage
        mbs_api_usage_plan.add_api_stage(
            stage=mbsapi.deployment_stage,
        )

        #Grant neptune read via query to mbsget lambda
        mbs_get_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=['neptune-db:ReadDataViaQuery'],
            resources=[neptune_arn],
            effect=iam.Effect.ALLOW,
            ))