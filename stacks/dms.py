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

from aws_cdk import (
    aws_iam as iam,
    aws_s3 as s3, 
    aws_ec2 as ec2,
    Stack,
    aws_dms as dms,
    RemovalPolicy,
)

import os
import json
import boto3
import csv

from constructs import Construct

class DMSStack(Stack):
    """
    Creates the DMS stack for our application needs
    """
    def __init__(self, scope: Construct, id: str, vpc, bucket, rds_secret, rds_database_name, neptune_endpoint, neptune_endpoint_role, **kwargs) -> None:

        super().__init__(scope, id, **kwargs)
        stack = Stack.of(self)

        dms_instance_class = 'dms.t3.micro'
        aurora_engine = "aurora-postgresql"

        # boto3 client for Secrets Manager
        sm_client = boto3.client("secretsmanager")

        subnet_ids = []
        selection = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        for subnet in selection.subnets:
            subnet_ids.append(subnet.subnet_id)
        
       

        #create replication subnet group
        replication_subnet_group_identifier = 'mbs-dms-subnetgroup'
        subnet = dms.CfnReplicationSubnetGroup(
                self,
                "dmsreplicationsubnetgrp",
                replication_subnet_group_identifier=replication_subnet_group_identifier,
                replication_subnet_group_description='DMS replication subnet group',
                subnet_ids=subnet_ids
        )
        #create a security group 
        security_group_db = ec2.SecurityGroup(
            self,
            "security_group_db",
            vpc=vpc,
            security_group_name="dms_security_group_db",
            allow_all_outbound=True,
        )

        
        #create S3 bucket for the DMS         
        s3_bucket = s3.Bucket(
            self, 
            id="dmsmigration", 
            bucket_name=bucket,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
               
        # Create replication instance per server
        replInstName = "rds2neptune"
        replInstIdentifier = "rds2neptune"
        replTaskName = "mbs-rds-neptune-migration"

        instance = dms.CfnReplicationInstance(
                    self,
                    replInstName,
                    replication_instance_identifier=replInstIdentifier,
                    replication_instance_class=dms_instance_class,
                    publicly_accessible=False,
                    #replication_subnet_group_identifier=subnet.ref,
                    replication_subnet_group_identifier=replication_subnet_group_identifier,                    
                    vpc_security_group_ids=[security_group_db.security_group_id],
                    auto_minor_version_upgrade=True,
                    multi_az=False,
                    engine_version='3.4.7'
        )

        # create source endpoint
        source_endpoint ='mbs-rds-ep'
        
        postgre_settings=dms.CfnEndpoint.PostgreSqlSettingsProperty(
                                secrets_manager_access_role_arn=neptune_endpoint_role.role_arn,
                                secrets_manager_secret_id=rds_secret.secret_arn
        )
        
        source = dms.CfnEndpoint(
                    self,
                    source_endpoint,
                    endpoint_identifier=source_endpoint,
                    endpoint_type='source',
                    engine_name=aurora_engine,
                    database_name='postgres',
                    postgre_sql_settings=postgre_settings,
        )

        # create target endpoint
        
        s3_prefix = "neptune/data"
        neptune_settings=dms.CfnEndpoint.NeptuneSettingsProperty(
            iam_auth_enabled=True,
            s3_bucket_folder=s3_prefix,
            s3_bucket_name=s3_bucket.bucket_name,
            service_access_role_arn=neptune_endpoint_role.role_arn
        )

        target_endpoint ='mbs-neptune-ep'
      
        target = dms.CfnEndpoint(
                    self,
                    target_endpoint,
                    endpoint_identifier=target_endpoint,
                    endpoint_type='target',
                    engine_name='neptune',
                    server_name=neptune_endpoint,
                    neptune_settings=neptune_settings,
                    port=8182        
        )

        #create the replication task
        source_mappings_location = 'resources/config/dms_json_mappings/source_mappings.json'
        target_mappings_location = 'resources/config/dms_json_mappings/target_mappings.json'
        replication_task_settings_location ='resources/config/task_settings/replication_task_settings.json'
        current_dir = os.getcwd()
        with open(os.path.join(current_dir, source_mappings_location.lower()), mode='r') as jsonfile:
            source_mappings_json = json.load(jsonfile)
            with open(os.path.join(current_dir, target_mappings_location.lower()), mode='r') as jsonfile:
                target_mappings_json = json.load(jsonfile)
                with open(os.path.join(current_dir, replication_task_settings_location.lower()), mode='r') as jsonfile:
                    replication_task_settings_json = json.load(jsonfile)
                    # create dms replication task
                    task = dms.CfnReplicationTask(
                            self,
                            replTaskName,
                            replication_task_identifier=replTaskName,
                            replication_instance_arn=instance.ref,
                            migration_type="full-load",
                            source_endpoint_arn=source.ref,
                            target_endpoint_arn=target.ref,
                            table_mappings=json.dumps(source_mappings_json),
                            task_data=json.dumps(target_mappings_json),
                            replication_task_settings=json.dumps(replication_task_settings_json)                            
                        )
