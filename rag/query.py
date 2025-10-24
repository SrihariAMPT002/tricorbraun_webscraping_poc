from langchain_community.vectorstores import Pinecone as LangPinecone
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
docsearch = LangPinecone.from_existing_index("products-index", embeddings)

query = "amber glass vial under 10 ml"
results = docsearch.similarity_search(query, k=3)

for r in results:
    print(f"🧴 {r.metadata['name']} — {r.metadata['url']}")
    print(r.page_content[:300])
    print("-" * 50)
