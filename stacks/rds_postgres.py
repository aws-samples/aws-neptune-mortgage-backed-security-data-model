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
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_lambda as _lambda,
    aws_events_targets as targets,
    aws_cloudwatch as cloudwatch,
    aws_secretsmanager as sm,
    aws_kms as kms,
    Stack,    
)
import json
#from aws_cdk import Duration, RemovalPolicy

from constructs import Construct

class RDSPostgresStack(Stack):
    """
    Creates the RDS postgress stack for our application needs
    """

    def __init__(self, 
                 scope: Construct, 
                 id: str, 
                 vpc, 
                 db_secret:str,
                 db_name:str, 
                 replica_instances:int = 1,
                 backup_retention_days:int=14,
                 backup_window:str="00:15-01:15",
                 preferred_maintenance_window:str="Sun:23:45-Mon:00:15",
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        #core variables
        aurora_engine = rds.DatabaseClusterEngine.aurora_postgres(version=rds.AuroraPostgresEngineVersion.VER_13_4)
        instance_type = ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM)
        
       
       # create RDS secret

        db_master_user_name = "postgres"
        self.rds_secret = sm.Secret(self, "MBSRDSSecret",
             secret_name=db_secret,
             generate_secret_string=sm.SecretStringGenerator(
                secret_string_template=json.dumps(
                    {"username": db_master_user_name}),
                exclude_punctuation=True,
                include_space=False,
                generate_string_key="password",
             )
        )

        # create a security group  and add ingress rule
        connection_name = "tcp5432 PostgreSQL"
        security_group_db = ec2.SecurityGroup(
            self,
            "security_group_db",
            vpc=vpc,
            security_group_name="security_group_db",
            allow_all_outbound=True,
        )

        #allow access to private subnet       
        selection = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        for subnet in selection.subnets:
           security_group_db.add_ingress_rule(peer=ec2.Peer.ipv4(subnet.ipv4_cidr_block), connection=ec2.Port.tcp(5432), description=connection_name)
        

        # create Parameter group for RDS postgress instance
        parameter_group_db = rds.ParameterGroup(
                self,
                "parameter_group_postgres",
                engine=aurora_engine,
                parameters={}
        )

        #create kms key and associate to this RDS instance
        kms_key = kms.Key(self, "MBSAuroraDatabaseKey",
            enable_key_rotation=True,
            alias=db_name
        )
            
        # create RDS Postgress instance
        aurora_cluster_credentials = rds.Credentials.from_secret(self.rds_secret, db_master_user_name)
        vpc_subnets=ec2.SubnetSelection( subnet_type=ec2.SubnetType.PRIVATE_ISOLATED )
        self.db = rds.DatabaseCluster(
            self,
            id = "AuroraPostgresDB",
            engine =aurora_engine,
            instance_identifier_base = db_name,
            parameter_group = parameter_group_db,
            instances = replica_instances,
            iam_authentication = True,
            storage_encrypted = True,
            storage_encryption_key = kms_key,
            deletion_protection=False,
            copy_tags_to_snapshot=True,
            instance_props = {
                "instance_type": instance_type,
                "vpc_subnets": vpc_subnets,
                "vpc": vpc,
                "security_groups": [security_group_db],
            },
            credentials=aurora_cluster_credentials,
        )
        
        cdk.CfnOutput(
            self,
            id = "DatabaseSecret",
            value = db_secret,
            description = "Database Secret String",
            export_name = f"{self.region}:{self.account}:{self.stack_name}:database-secret-string"
        )
