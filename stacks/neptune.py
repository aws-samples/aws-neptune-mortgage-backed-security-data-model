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

import os

import aws_cdk as cdk

from aws_cdk import (
  aws_ec2 as ec2,
  aws_s3 as s3,
  aws_neptune as neptune,
  aws_iam as iam,
  aws_kms as kms,
  Stack
)

from constructs import Construct

class NeptuneStack(Stack):
    """
    Creates the Neptune  stack for our application needs
    """

    def __init__(self, scope: Construct, id: str, vpc, bucket, **kwargs) -> None:
        
        super().__init__(scope, id, **kwargs)

        #create the security groups
        sg_use_graph_db = ec2.SecurityGroup(self, "NeptuneClientSG",
          vpc=vpc,
          allow_all_outbound=True,
          description='security group for neptune client lambda process',
          security_group_name='lambda-neptune-SG'
        )
        cdk.Tag('Name', 'lambda-neptune-SG').visit(sg_use_graph_db)

        sg_graph_db = ec2.SecurityGroup(self, "NeptuneSG",
          vpc=vpc,
          allow_all_outbound=True,
          description='security group for neptune',
          security_group_name='neptune-SG'
        )
        cdk.Tag('Name', 'neptune-SG').visit(sg_graph_db)

        sg_graph_db.add_ingress_rule(peer=sg_graph_db, connection=ec2.Port.tcp(8182), description='neptune-inbound')
        sg_graph_db.add_ingress_rule(peer=sg_use_graph_db, connection=ec2.Port.tcp(8182), description='neptune-inbound')
        

        selection = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        for subnet in selection.subnets:
           print (subnet)
           sg_graph_db.add_ingress_rule(peer=ec2.Peer.ipv4(subnet.ipv4_cidr_block), connection=ec2.Port.tcp(8182), description='neptune-inbound')

        #create the DB Subnet group
        graph_db_subnet_group = neptune.CfnDBSubnetGroup(self, 'NeptuneSubnetGroup',
          db_subnet_group_description='subnet group for neptune',
          subnet_ids=vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED).subnet_ids,
          db_subnet_group_name='neptune-DB-subnet-group'
        )

        

        #create assoicated IAM role
        self.neptune_access_role = iam.Role(self,
            "neptune_endpoint_access_role",
            assumed_by=iam.CompositePrincipal(
                        iam.ServicePrincipal("dms.amazonaws.com"),
                        iam.ServicePrincipal("dms.us-east-1.amazonaws.com"),
                        iam.ServicePrincipal("rds.amazonaws.com"),
            )
        )
        
       
        s3_resource_objects_arn = f"arn:aws:s3:::{bucket}/*"
        s3_resource_arn = f"arn:aws:s3:::{bucket}"
        
        self.neptune_access_role.add_to_policy(iam.PolicyStatement(
            resources=[s3_resource_arn, s3_resource_objects_arn],
            actions=["s3:GetObject", "s3:ListBucket", "s3:PutObject", "s3:DeleteObject", "s3:GetBucketLocation"]
        ))

        secret_arn = f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:rds/MBS*"
        self.neptune_access_role.add_to_policy(iam.PolicyStatement(
            resources=[secret_arn],
            actions=["secretsmanager:GetSecretValue"]
        ))


        #create a KMS key
        kms_key = kms.Key(self, "MBSNeptuneDatabaseKey",
            enable_key_rotation=True
        )

        #create the Neptune cluster
        self.graph_db = neptune.CfnDBCluster(self, 'MBS-Neptune',
          db_subnet_group_name=graph_db_subnet_group.db_subnet_group_name,
          db_cluster_identifier='MBS-Neptune',
          backup_retention_period=1,
          preferred_backup_window='08:45-09:15',
          preferred_maintenance_window='sun:18:00-sun:18:30',
          vpc_security_group_ids=[sg_graph_db.security_group_id],
          associated_roles=[neptune.CfnDBCluster.DBClusterRoleProperty(
                       role_arn=self.neptune_access_role.role_arn
          )],
          iam_auth_enabled=True,
          storage_encrypted=True,
          kms_key_id=kms_key.key_id
        )

        #restrict the access to only this particular resource and actions
        self.neptune_resource_arn = f"arn:aws:neptune-db:{self.region}:{self.account}:{self.graph_db.attr_cluster_resource_id}/*"
        self.neptune_access_role.add_to_policy(iam.PolicyStatement(
            resources=[self.neptune_resource_arn],
            actions=["neptune-db:Get*", "neptune-db:List*", "neptune-db:Write*", "neptune-db:Read*", "neptune-db:connect*", "neptune-db:Start*"]
        ))


        self.graph_db.add_depends_on(graph_db_subnet_group)
        
        
        cdk.CfnOutput(
            self,
            id="NeptuneEndpoint",
            value=self.graph_db.attr_endpoint,
            description="Neptune Database Writer Endpoint",
            export_name=f"{self.region}:{self.account}:{self.stack_name}:Neptune-Write-Endpoint"
        )
        
        #create an DB instance and add to the Neptune cluster
        self.graph_db_instance = neptune.CfnDBInstance(self, 'MBS-Neptune-Instance',
          db_instance_class='db.t3.medium',
          allow_major_version_upgrade=False,
          auto_minor_version_upgrade=False,
          db_cluster_identifier=self.graph_db.db_cluster_identifier,
          db_instance_identifier='MBS-Neptune-Instance',
          preferred_maintenance_window='sun:18:00-sun:18:30',
        )
        
        self.graph_db_instance.add_depends_on(self.graph_db)

