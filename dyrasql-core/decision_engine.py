#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Decision Engine - Implements the routing decision algorithm.
Score: S = w1×fv + w2×fc + w3×fh (volume, complexity, historical).
"""

import math
import logging
import os

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Computes routing score and selects the target cluster."""

    
    def __init__(self):

                                                                            
        self.w1 = float(os.getenv('DYRASQL_WEIGHT_VOLUME', '0.5'))                        

        self.w2 = float(os.getenv('DYRASQL_WEIGHT_COMPLEXITY', '0.3'))                              

        self.w3 = float(os.getenv('DYRASQL_WEIGHT_HISTORICAL', '0.2'))                           

        
        self.ecs_threshold = float(os.getenv('DYRASQL_ECS_THRESHOLD', '0.3'))

        self.emr_standard_threshold = float(os.getenv('DYRASQL_EMR_STANDARD_THRESHOLD', '0.7'))

        
        total_weight = self.w1 + self.w2 + self.w3

        if abs(total_weight - 1.0) > 0.1:
            logger.warning("decision_engine weights sum=%.2f (expected 1.0)", total_weight)

        logger.info("decision_engine configured w1=%.2f w2=%.2f w3=%.2f ecs_threshold=%.2f emr_standard_threshold=%.2f",
            self.w1, self.w2, self.w3, self.ecs_threshold, self.emr_standard_threshold)

    
    def decide(self, query, fingerprint, metadata, complexity, history_manager):
        """Runs the full decision algorithm. Returns routing decision with score and cluster."""

                                    
        fv = self._calculate_volume_factor(metadata)

        
        fc = self._calculate_complexity_factor(complexity)

        
        fh = history_manager.get_historical_factor(fingerprint, query)

        
        score = self.w1 * fv + self.w2 * fc + self.w3 * fh

        
        cluster = self._select_cluster(score)

        
        decision = {

            'cluster': cluster,

            'score': score,

            'factors': {

                'volume': fv,

                'complexity': fc,

                'historical': fh

            }

        }

        
        logger.info("decision cluster=%s score=%.3f", cluster, score)

        return decision

    
    def _calculate_volume_factor(self, metadata):
        """
        Volume factor from EXPLAIN (TYPE IO) table metadata.
        fv = (log(Ae) + log(Te)) / (2 * log(Lm)) * (1 - Fo); Ae=effective files, Te=size GB, Lm=limit, Fo=optimization.
        """

        if not metadata:

            return 0.5                                        

        
        total_size_bytes = sum(m.get('total_size_bytes', 0) for m in metadata.values())

        total_rows = sum(m.get('total_records', 0) for m in metadata.values())

        total_size_gb = total_size_bytes / (1024**3)

        
        avg_file_size_mb = 50

        estimated_files = max(1, int((total_size_gb * 1024) / avg_file_size_mb))

        
        effective_files = estimated_files

        effective_size_gb = total_size_gb

        
        max_files = 10000

        max_size_gb = 1000                          

        
        optimization_factor = 0.1                                                

        
        if effective_files < 1:

            effective_files = 1

        if effective_size_gb < 0.001:

            effective_size_gb = 0.001

        
        log_files = math.log(effective_files)

        log_size = math.log(effective_size_gb)

        log_max_files = math.log(max_files)

        log_max_size = math.log(max_size_gb)

        
        normalized_files = min(1.0, log_files / log_max_files)

        normalized_size = min(1.0, log_size / log_max_size)

        
        fv = (normalized_files * 0.3 + normalized_size * 0.7) * (1 - optimization_factor)

        
        fv = max(0, min(1, fv))

        
        logger.debug("volume_factor files=%s size_gb=%.2f rows=%s fv=%.3f", estimated_files, total_size_gb, total_rows, fv)

        return fv

    
    def _calculate_complexity_factor(self, complexity):
        """Complexity factor from query analysis: fc = (J×0.2 + Ag×0.15 + Sq×0.25 + Fp×0.02 + Fnp×0.1) / Lc."""

        joins = complexity.get('joins', 0)

        aggregations = complexity.get('aggregations', 0)

        subqueries = complexity.get('subqueries', 0)

        partitioned_filters = complexity.get('partitioned_filters', 0)

        non_partitioned_filters = complexity.get('non_partitioned_filters', 0)

        
        complexity_limit = 2.0

        
        fc = (

            joins * 0.2 +

            aggregations * 0.15 +

            subqueries * 0.25 +

            partitioned_filters * 0.02 +

            non_partitioned_filters * 0.1

        ) / complexity_limit

        
        fc = max(0, min(1, fc))

        
        logger.debug("complexity_factor joins=%s aggs=%s fc=%.3f", joins, aggregations, fc)

        return fc

    
    def _select_cluster(self, score):
        """Selects cluster by score: < 0.3 ECS, 0.3–0.7 EMR Standard, > 0.7 EMR Optimized."""

        if score < self.ecs_threshold:

            return 'ecs'

        elif score <= self.emr_standard_threshold:

            return 'emr-standard'

        else:

            return 'emr-optimized'

