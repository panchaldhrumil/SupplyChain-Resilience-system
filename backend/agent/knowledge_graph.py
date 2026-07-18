"""
backend/agent/knowledge_graph.py
================================
Lightweight Knowledge Graph — TIER 2

Explicit graph structure built from configuration files:
- Nodes:
  - Countries (Suppliers)
  - Corridors (Chokepoints)
  - Ports (Crude-receiving terminals)
  - Refineries
- Edges:
  - supplies_via (Country → Corridor)
  - transits (Corridor → Port)
  - feeds (Port → Refinery)

Provides programmatic graph traversal to determine which suppliers, ports, and
refineries are exposed when a given corridor experiences a disruption, replacing
hardcoded mapping with traversal.
"""

import json
from pathlib import Path

# Static infrastructure coordinates and linkages
PORT_TO_REFINERY = {
    "port_vadinar":  ["Nayara Vadinar"],
    "port_sikka":    ["Reliance Jamnagar"],
    "port_kandla":   ["Koyali Refinery", "Mathura Refinery"],  # North India feed
    "port_paradip":  ["IOCL Paradip"],
    "port_vizag":    ["HPCL Vizag"],
    "port_mumbai":   ["HPCL/BPCL Mumbai"],
    "port_kochi":    ["BPCL Kochi"],
}

CORRIDOR_TO_PORTS = {
    "hormuz":            ["port_vadinar", "port_sikka", "port_kandla", "port_mumbai", "port_kochi"],
    "red_sea":           ["port_vadinar", "port_sikka", "port_kandla", "port_mumbai", "port_kochi"],
    "suez":              ["port_vadinar", "port_sikka", "port_kandla", "port_mumbai", "port_kochi"],
    "cape_of_good_hope": ["port_mumbai", "port_kochi", "port_paradip", "port_vizag"],
    "russia_route":      ["port_vadinar", "port_sikka", "port_paradip", "port_vizag"],
    "malacca":           ["port_paradip", "port_vizag"],
    "india_domestic":    ["port_vadinar", "port_sikka", "port_paradip", "port_vizag", "port_mumbai", "port_kochi"],
}


class LightweightKnowledgeGraph:
    def __init__(self, config_dir: Path):
        self.nodes = {
            "country":  set(),
            "corridor": set(CORRIDOR_TO_PORTS.keys()),
            "port":     set(PORT_TO_REFINERY.keys()),
            "refinery": set()
        }
        # Adjacency list: node -> set of (neighbor, relationship_type)
        self.adj = {}

        # Parse refineries
        for refs in PORT_TO_REFINERY.values():
            for ref in refs:
                self.nodes["refinery"].add(ref)

        self._build_graph(config_dir)

    def _add_edge(self, u: str, v: str, rel: str):
        if u not in self.adj:
            self.adj[u] = []
        self.adj[u].append((v, rel))

    def _build_graph(self, config_dir: Path):
        # 1. Edges: transits (Corridor -> Port)
        for corridor, ports in CORRIDOR_TO_PORTS.items():
            for port in ports:
                self._add_edge(corridor, port, "transits")

        # 2. Edges: feeds (Port -> Refinery)
        for port, refineries in PORT_TO_REFINERY.items():
            for refinery in refineries:
                self._add_edge(port, refinery, "feeds")

        # 3. Edges: supplies_via (Country -> Corridor)
        # Loaded from scenario_assumptions.json (country_chokepoints)
        assumptions_path = config_dir / "scenario_assumptions.json"
        if assumptions_path.exists():
            try:
                with open(assumptions_path, encoding="utf-8") as f:
                    assumptions = json.load(f)
                country_chokepoints = assumptions.get("country_chokepoints", {})
                for country, corridors in country_chokepoints.items():
                    if country.startswith("_"):
                        continue
                    self.nodes["country"].add(country)
                    for corridor in corridors:
                        # Edge direction matches supply flow: Country -> Corridor
                        self._add_edge(country, corridor, "supplies_via")
            except Exception:
                pass

    def traverse_disruption(self, disrupted_corridor: str) -> dict:
        """
        Traverse the graph to find nodes affected by a chokepoint closure.
        
        1. Find affected countries (Suppliers):
           Any Country node that has a 'supplies_via' edge pointing to disrupted_corridor.
           
        2. Find affected Ports:
           Directly reachable from disrupted_corridor via 'transits' edges.
           
        3. Find affected Refineries:
           Reachable from affected Ports via 'feeds' edges.
        """
        affected_countries = []
        # Reverse check supplies_via edges
        for country in self.nodes["country"]:
            edges = self.adj.get(country, [])
            for neighbor, rel in edges:
                if neighbor == disrupted_corridor and rel == "supplies_via":
                    affected_countries.append(country)

        # Forward traversal from corridor -> ports
        affected_ports = CORRIDOR_TO_PORTS.get(disrupted_corridor, [])

        # Forward traversal from ports -> refineries
        affected_refineries = []
        for port in affected_ports:
            refs = PORT_TO_REFINERY.get(port, [])
            for ref in refs:
                if ref not in affected_refineries:
                    affected_refineries.append(ref)

        return {
            "affected_suppliers":  affected_countries,
            "affected_ports":      affected_ports,
            "affected_refineries": affected_refineries,
        }
