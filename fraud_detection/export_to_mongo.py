"""
Export FraudGraph data to a MongoDB server.
"""

import logging
from typing import Any

import pymongo

from fraud_detection.graph.schema import FraudGraph

logger = logging.getLogger(__name__)

MONGODB_URI = "mongodb+srv://parthnark:abc@cluster0.kqnzdjt.mongodb.net/"
MONGODB_DB_NAME = "fraus"

def export_graph_to_mongo(
    fg: FraudGraph,
    collection_name: str = "graph_data"
) -> None:
    """Export the FraudGraph to MongoDB."""
    client = pymongo.MongoClient(MONGODB_URI)
    db = client[MONGODB_DB_NAME]
    collection = db[collection_name]
    
    # Clear existing data
    collection.drop()
    
    # Insert nodes
    nodes = []
    for nid, data in fg._g.nodes(data=True):
        node_doc = {"_id": nid, "type": "node", **data}
        nodes.append(node_doc)
    if nodes:
        collection.insert_many(nodes)
    
    # Insert edges
    edges = []
    for u, v, data in fg._g.edges(data=True):
        edge_doc = {"_id": f"{u}-->{v}", "type": "edge", "source": u, "target": v, **data}
        edges.append(edge_doc)
    if edges:
        collection.insert_many(edges)
    
    logger.info("Exported %d nodes and %d edges to MongoDB %s.%s", len(nodes), len(edges), MONGODB_DB_NAME, collection_name)
    client.close()


if __name__ == "__main__":
    # Example usage: generate synthetic data and export
    from fraud_detection.data.synthetic import generate_fraud_ring_dataset
    
    dataset = generate_fraud_ring_dataset()
    fg = dataset["graph"]
    export_graph_to_mongo(fg)