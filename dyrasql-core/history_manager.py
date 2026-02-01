#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
History Manager - Manages routing decision cache and history in DynamoDB.
"""

import os
import boto3
import json
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class HistoryManager:
    """Manages decision cache and history in DynamoDB."""

    
    def __init__(self):

        self.table_name = os.getenv('DYNAMODB_TABLE', 'dyrasql-history')

        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')

        self.aws_profile = os.getenv('AWS_PROFILE', 'default')

        self.cache_ttl_hours = 24

        
        try:

            session = boto3.Session(profile_name=self.aws_profile)

            self.dynamodb = session.resource('dynamodb', region_name=self.aws_region)

            self.table = self.dynamodb.Table(self.table_name)

            logger.info("history_manager dynamodb_connected table=%s profile=%s", self.table_name, self.aws_profile)

        except Exception as e:
            logger.error("history_manager dynamodb_connect_failed error=%s", str(e))

            self.table = None

    
    def get_cached_decision(self, fingerprint):
        """Returns cached decision for fingerprint if TTL is still valid (24h)."""

        if not self.table:

            return None

        
        try:

            response = self.table.get_item(

                Key={'fingerprint': fingerprint}

            )

            
            if 'Item' not in response:

                return None

            
            item = response['Item']

            
            ttl = item.get('ttl', 0)

            current_time = int(time.time())

            
            if ttl > current_time:

                logger.debug("cache_hit fingerprint=%s", fingerprint[:16])

                
                factors_str = item.get('factors', '{}')

                try:

                    factors = json.loads(factors_str) if isinstance(factors_str, str) else factors_str

                except (json.JSONDecodeError, TypeError):

                    factors = {}

                
                return {

                    'cluster': item.get('cluster'),

                    'score': float(item.get('score', 0)),

                    'factors': factors,

                    'timestamp': item.get('timestamp')

                }

            else:

                logger.debug("cache_expired fingerprint=%s", fingerprint[:16])

                return None

                
        except Exception as e:

            logger.error("get_cached_decision error=%s", str(e))

            return None

    
    def save_decision(self, fingerprint, decision):
        """Saves a decision to DynamoDB with 24h TTL."""

        if not self.table:

            logger.warning("save_decision skipped dynamodb_unavailable")

            return

        
        try:

            current_time = int(time.time())

            ttl = current_time + (self.cache_ttl_hours * 3600)

            
            item = {

                'fingerprint': fingerprint,

                'cluster': decision['cluster'],

                'score': str(decision['score']),

                'factors': json.dumps(decision.get('factors', {})),

                'timestamp': datetime.utcnow().isoformat(),

                'ttl': ttl

            }

            
            self.table.put_item(Item=item)

            logger.debug("decision_saved fingerprint=%s", fingerprint[:16])

            
        except Exception as e:

            logger.error("save_decision error=%s", str(e))

    
    def save_metrics(self, metrics_data):
        """Saves post-execution metrics to DynamoDB."""

        if not self.table:

            logger.warning("save_metrics skipped dynamodb_unavailable")

            return

        
        try:

            fingerprint = metrics_data['fingerprint']

            
            update_expression = "SET execution_time = :et, cost = :c, success = :s, updated_at = :ua"

            expression_values = {

                ':et': metrics_data.get('execution_time', 0),

                ':c': metrics_data.get('cost', 0),

                ':s': metrics_data.get('success', True),

                ':ua': datetime.utcnow().isoformat()

            }

            
            self.table.update_item(

                Key={'fingerprint': fingerprint},

                UpdateExpression=update_expression,

                ExpressionAttributeValues=expression_values

            )

            
            logger.debug("metrics_saved fingerprint=%s", fingerprint[:16])

            
        except Exception as e:

            logger.error("save_metrics error=%s", str(e))

    
    def get_historical_factor(self, fingerprint, query):
        """Computes historical factor from similar queries. Returns value in [0, 1]."""

        if not self.table:

            return 0.5                                        

        
        try:

                                                           
            response = self.table.get_item(

                Key={'fingerprint': fingerprint}

            )

            
            if 'Item' not in response:

                return 0.5                                        

            
            item = response['Item']

            
            previous_score = float(item.get('score', 0.5))

            
            success = item.get('success', True)

            if success:

                return previous_score

            else:

                                                               
                return 1.0 - previous_score

            
        except Exception as e:

            logger.warning("get_historical_factor error=%s", str(e))

            return 0.5                                

