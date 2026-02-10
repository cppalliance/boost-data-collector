"""
CPPA Pinecone Sync: upserts, updates, and deletes documents in Pinecone
on behalf of other apps. Other apps call sync_to_pinecone() with a type,
namespace, and preprocessing function; this app handles Pinecone I/O,
failure tracking (PineconeFailList), and sync status (PineconeSyncStatus).
"""
