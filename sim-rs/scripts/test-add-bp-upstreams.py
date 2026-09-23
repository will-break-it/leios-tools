#!/usr/bin/env python3
"""Checks for the BP upstream derivation used by the three-upstream matrix."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, HERE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bpup = load('bpup', 'add-bp-upstreams.py')


def fixture(clusters=6):
    """Clusters of one producer beside two relays, plus spare relays.

    Every producer sits at its cluster's longitude so that a nearest-only rule
    has an obvious hub to collapse onto: the spare relays all sit at longitude 0.
    """
    nodes = {}
    for index in range(clusters):
        bp, a, b = f'bp-{index}', f'relay-{index}a', f'relay-{index}b'
        lon = float(index)
        for name in (a, b):
            nodes[name] = {'location': [lon, 0.0], 'cpu-core-count': 4, 'stake': 0,
                           'producers': {bp: {'bandwidth-bytes-per-second': 125000000,
                                              'latency-ms': 0.2}}}
        nodes[bp] = {'location': [lon, 0.0], 'cpu-core-count': 4, 'stake': 1000 + index,
                     'producers': {a: {'bandwidth-bytes-per-second': 125000000, 'latency-ms': 0.2},
                                   b: {'bandwidth-bytes-per-second': 125000000, 'latency-ms': 0.3}}}
    for spare in range(clusters):
        nodes[f'spare-{spare}'] = {
            'location': [0.0, 0.0], 'cpu-core-count': 4, 'stake': 0,
            'producers': {'relay-0a': {'bandwidth-bytes-per-second': 125000000,
                                       'latency-ms': 5.0 + spare}}}
    return {'nodes': nodes}


def producers(topology):
    return [n for n, v in topology['nodes'].items() if v.get('stake', 0)]


class AddUpstreams(unittest.TestCase):
    def test_every_producer_reaches_the_target_degree(self):
        topology = fixture()
        added = bpup.add_upstreams(topology, 3)
        self.assertEqual(added, len(producers(topology)))
        for bp in producers(topology):
            self.assertEqual(len(topology['nodes'][bp]['producers']), 3)

    def test_added_links_are_reciprocal_and_never_reach_a_producer(self):
        topology = fixture()
        bpup.add_upstreams(topology, 3)
        nodes = topology['nodes']
        for bp in producers(topology):
            for relay in nodes[bp]['producers']:
                self.assertFalse(nodes[relay].get('stake', 0), f'{relay} holds stake')
                self.assertIn(bp, nodes[relay]['producers'],
                              f'{relay} does not list {bp} back')

    def test_selection_is_balanced_rather_than_collapsing_onto_one_relay(self):
        topology = fixture()
        bpup.add_upstreams(topology, 3)
        nodes = topology['nodes']
        serving = {}
        for bp in producers(topology):
            for relay in nodes[bp]['producers']:
                serving[relay] = serving.get(relay, 0) + 1
        # Each producer keeps its own two relays; the added link must land on a
        # relay that is not already serving one, while spares remain.
        self.assertEqual(max(serving.values()), 1)

    def test_copy_latency_reuses_the_producers_existing_link(self):
        topology = fixture()
        bpup.add_upstreams(topology, 3, latency='copy')
        nodes = topology['nodes']
        for bp in producers(topology):
            latencies = {link['latency-ms'] for link in nodes[bp]['producers'].values()}
            self.assertTrue(latencies <= {0.2, 0.3}, latencies)

    def test_sampled_latency_comes_from_the_source_pool(self):
        topology = fixture()
        pool = {link['latency-ms'] for node in topology['nodes'].values()
                for link in node['producers'].values()}
        original = {bp: set(topology['nodes'][bp]['producers']) for bp in producers(topology)}
        bpup.add_upstreams(topology, 3)
        for bp, before in original.items():
            for relay, link in topology['nodes'][bp]['producers'].items():
                if relay not in before:
                    self.assertIn(link['latency-ms'], pool)
                    self.assertEqual(link['bandwidth-bytes-per-second'], 125000000)

    def test_target_equal_to_the_current_degree_changes_nothing(self):
        topology = fixture()
        before = copy.deepcopy(topology)
        self.assertEqual(bpup.add_upstreams(topology, 2), 0)
        self.assertEqual(topology, before)

    def test_a_target_below_the_current_degree_is_rejected(self):
        with self.assertRaises(ValueError):
            bpup.add_upstreams(fixture(), 1)

    def test_a_topology_without_producers_is_rejected(self):
        topology = fixture()
        for node in topology['nodes'].values():
            node['stake'] = 0
        with self.assertRaises(ValueError):
            bpup.add_upstreams(topology, 3)

    def test_exhausting_the_relays_is_an_error_rather_than_a_producer_upstream(self):
        topology = fixture(clusters=2)
        # Two clusters give four relays plus two spares; ask for more than that.
        with self.assertRaises(ValueError):
            bpup.add_upstreams(topology, 7)

    def test_derivation_is_deterministic(self):
        first, second = fixture(), fixture()
        bpup.add_upstreams(first, 3)
        bpup.add_upstreams(second, 3)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))


class StudyRunnerIntegration(unittest.TestCase):
    def test_runner_marks_every_derived_upstream_and_checks_the_degree(self):
        runner = load('runner', 'vote-diffusion-study.py')
        topology = runner.study_topology('1500', 3)
        nodes = topology['nodes']
        bps = [n for n, v in nodes.items() if v.get('stake', 0)]
        self.assertTrue(bps)
        for bp in bps:
            peers = nodes[bp]['producers']
            self.assertEqual(len(peers), 3)
            for relay, link in peers.items():
                self.assertTrue(link['always-forward-votes'])
                self.assertFalse(nodes[relay].get('stake', 0))
                self.assertEqual(link['bandwidth-bytes-per-second'], 1250000)

    def test_default_upstream_count_keeps_the_published_topology(self):
        runner = load('runner', 'vote-diffusion-study.py')
        self.assertEqual(json.dumps(runner.study_topology('1500'), sort_keys=True),
                         json.dumps(runner.study_topology('1500', 2), sort_keys=True))

    def test_a_protected_cap_must_cover_the_busiest_relay(self):
        """The derived topology must not need a cap larger than the ones tested."""
        runner = load('runner', 'vote-diffusion-study.py')
        nodes = runner.study_topology('1500', 3)['nodes']
        serving = {}
        for name, node in nodes.items():
            if node.get('stake', 0):
                for relay in node['producers']:
                    serving[relay] = serving.get(relay, 0) + 1
        self.assertLessEqual(max(serving.values()), 8)


if __name__ == '__main__':
    unittest.main(verbosity=1)
