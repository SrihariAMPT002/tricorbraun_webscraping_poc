from chatbot_production import HybridRAGChatbot
chat = HybridRAGChatbot(verbose=False, log_file="Logs/chatbot_activity.log")
query = "How many products have a blank (empty) color field?"
response = chat.query(query)
chat.export_logs("Logs/query_logs.json")
print("📤 RESPONSE:")
print(response)
