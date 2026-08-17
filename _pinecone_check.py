from dotenv import load_dotenv
load_dotenv(".env")
from rag.vector_store import get_pinecone_client, get_index_name, get_namespace
idx = get_pinecone_client().index(get_index_name())
ns = get_namespace()
z = [0.0] * 1536
eq = "$eq"
for d in ["hhs_physical_activity_guidelines_2e","healthcoach_trend_detection","healthcoach_correlation_modeling","healthcoach_safety_scope_escalation"]:
    n = len(idx.query(vector=z, top_k=10000, namespace=ns, filter={"document_id": {eq: d}}).matches or [])
    print(d, n)
print("namespace_total", idx.describe_index_stats().namespaces[ns].vector_count)
