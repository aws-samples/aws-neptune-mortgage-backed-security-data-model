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
#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.vpc import VpcStack
from stacks.rds_postgres import RDSPostgresStack
from stacks._lambda import LambdaStack
from stacks.neptune import NeptuneStack
from stacks.dms import DMSStack
from stacks.iam import IamStack

#initialize the env and other variables
env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION'))
database_name= 'MBS'
rds_secret = f"rds/{database_name}"

app = cdk.App()

#create VPC and subnets
vpc_ec2_stack = VpcStack(
    scope=app,
    id="VPC",
    env=env
)

#create the RDS DB
postgres = RDSPostgresStack(
    scope=app,
    id="AuroraPostgresDB",
    vpc=vpc_ec2_stack.vpc,
    db_secret=rds_secret,
    db_name=database_name,
    env=env
)


#create the Neptune DB
bucket_name= f'{env.account}-dmsmigration'

neptune = NeptuneStack(
    scope=app,
    id="NeptuneDB",
    vpc=vpc_ec2_stack.vpc,
    bucket=bucket_name,
    env=env
)

neptune_endpoint = neptune.graph_db.attr_endpoint

#create DMS dms-vpc-role not required if 
iam = IamStack(
    scope=app,
    id="iamroles",
    env=env
)

#create DMS - replication instance, task, source and target endpoints
dms  = DMSStack(
    scope=app,
    id="DMSResources",
    vpc=vpc_ec2_stack.vpc,
    bucket=bucket_name,
    rds_secret=postgres.rds_secret,
    rds_database_name=database_name,
    neptune_endpoint=neptune_endpoint,
    neptune_endpoint_role=neptune.neptune_access_role,
    env=env
)

#create the lambda and its associated API
lambda_stack = LambdaStack(
    scope=app,
    id="lambda",
    vpc=vpc_ec2_stack.vpc,
    rds_secret=postgres.rds_secret,
    rds_database_name=database_name,
    neptune_endpoint=neptune_endpoint,
    neptune_endpoint_role=neptune.neptune_access_role,
    neptune_arn=neptune.neptune_resource_arn,
    env=env
)
app.synth()
