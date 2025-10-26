from langchain_community.vectorstores import Pinecone as LangPinecone
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

# from langchain_community.embeddings import HuggingFaceEmbeddings

# Load environment variables from .env file
load_dotenv()
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

# embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

docsearch = LangPinecone.from_existing_index("products-index", embeddings)

query = "show me 10oz beer bottles"
results = docsearch.similarity_search(query, k=3)

for r in results:
    print(f"🧴 {r.metadata['name']} — {r.metadata['url']}")
    print(r.page_content[:300])
    print("-" * 50)
