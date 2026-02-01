#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Metadata Connector - Connects to Apache Iceberg tables and extracts metadata.
"""

import os
import boto3
import logging
from pyiceberg.catalog import load_catalog

logger = logging.getLogger(__name__)


class MetadataConnector:
    """Connects to Iceberg catalogs and extracts table metadata."""

    
    def __init__(self):

        self.s3_bucket = os.getenv('S3_BUCKET')

        self.s3_prefix = os.getenv('S3_PREFIX', 'iceberg/')

        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')

        self.aws_profile = os.getenv('AWS_PROFILE', 'default')

        
        session = boto3.Session(profile_name=self.aws_profile)

        self.s3_client = session.client('s3', region_name=self.aws_region)

        
        self.catalog = None

                                                                                 
    def get_metadata(self, table_name):
        """Extracts metadata for an Iceberg table. Returns file_count, total_size, record_count, partition_info, column_stats."""

        try:

                                                       
            if self.catalog:

                return self._get_metadata_from_catalog(table_name)

            else:

                                                              
                return self._get_metadata_from_s3(table_name)

        except Exception as e:

            logger.error("get_metadata error table=%s error=%s", table_name, str(e))

            return None

    
    def _get_metadata_from_catalog(self, table_name):
        """Extracts metadata using Iceberg catalog."""

        try:

                                                               
            parts = table_name.split('.')

            if len(parts) == 2:

                database, table = parts

            else:

                database = 'default'

                table = table_name

            
            iceberg_table = self.catalog.load_table((database, table))

            
            metadata = {

                'file_count': iceberg_table.metadata().current_snapshot().summary().get('total-data-files', 0),

                'total_size': iceberg_table.metadata().current_snapshot().summary().get('total-records', 0) * 100,              

                'record_count': iceberg_table.metadata().current_snapshot().summary().get('total-records', 0),

                'partition_info': self._extract_partition_info(iceberg_table),

                'column_stats': {}                      

            }

            
            return metadata

        except Exception as e:

            logger.warning("catalog_metadata_failed falling_back_to_s3 error=%s", str(e))

            return self._get_metadata_from_s3(table_name)

    
    def _get_metadata_from_s3(self, table_name):
        """
        Extracts metadata directly from S3. Expected layout: s3://bucket/{S3_PREFIX}/{table_name}/data/ and metadata/.
        """

        try:

                                              
            table_path = f"{self.s3_prefix.rstrip('/')}/{table_name}/"

            data_path = f"{table_path}data/"

            metadata_path = f"{table_path}metadata/"

            
            data_response = self.s3_client.list_objects_v2(

                Bucket=self.s3_bucket,

                Prefix=data_path

            )

            
            metadata_response = self.s3_client.list_objects_v2(

                Bucket=self.s3_bucket,

                Prefix=metadata_path

            )

            
            data_files = []

            if 'Contents' in data_response:

                data_files = [obj for obj in data_response['Contents'] 

                             if not obj['Key'].endswith('/')]                     

            
            metadata_files = []

            if 'Contents' in metadata_response:

                metadata_files = [obj for obj in metadata_response['Contents']

                                if obj['Key'].endswith('.metadata.json')]

            
            total_size = sum(obj['Size'] for obj in data_files)

            
            metadata = {

                'file_count': len(data_files),

                'total_size': total_size,

                'record_count': 0,                                              

                'partition_info': {},

                'column_stats': {},

                'metadata_files_count': len(metadata_files)

            }

            
            logger.debug("metadata_from_s3 path=%s file_count=%s size=%s", table_path, metadata.get('file_count'), metadata.get('total_size'))

            return metadata

            
        except Exception as e:

            logger.error("get_metadata_s3 error table=%s error=%s", table_name, str(e))

            return None

    
    def _extract_partition_info(self, iceberg_table):
        """Extracts partition info from Iceberg table."""

        try:

            partition_spec = iceberg_table.spec()

            partitions = []

            
            for field in partition_spec.fields:

                partitions.append({

                    'field': field.name,

                    'transform': str(field.transform)

                })

            
            return partitions

        except Exception as e:

            logger.warning("extract_partition_info error=%s", str(e))

            return {}

